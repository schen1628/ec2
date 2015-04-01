#!/usr/bin/python

import boto.ec2
import boto.ec2.elb
import croniter
import datetime
from time import sleep
import dateutil.parser
import pytz
import argparse
import logging
import logging.handlers

logger = logging.getLogger(__name__)

# Default window sizes to avoid missing a stop/start if a cron run misses or is off substantially from script runs.
# Instances will not be stopped again if they have been restarted since the beginning of the current stop period
start_window_size_minutes = 10
stop_window_size_minutes = 60


def time_to_start(schedule, now):
    # Round 'now' down and subtract one second so if the script is called at e.g. 05:00 and auto:start is 05:00,
    # croniter gives us this 05:00 run instead of the next. Otherwise, if this runs at 5:00 instances wouldn't start
    cron = croniter.croniter(schedule, now - datetime.timedelta(0, now.second + 1))
    window_end = now + datetime.timedelta(0, start_window_size_minutes * 60)
    cron_time = cron.get_next(datetime.datetime)
    logger.debug("now <= cron_time <= window_end = %s < %s < %s", now, window_end, cron_time)
    return (now <= cron_time <= window_end)


def time_to_stop(schedule, now, launch_time):
    # Round 'now' up to the next minute so if the script is called at e.g. 05:00 and auto:stop is 05:00, croniter
    # gives us this 05:00 run instead of the last one, and we shut down the instance on time.
    cron = croniter.croniter(schedule, now + datetime.timedelta(0, 60 - now.second))
    window_start = now - datetime.timedelta(0, stop_window_size_minutes * 60)
    cron_time = cron.get_prev(datetime.datetime)
    logger.debug("window_start <= cron_time <= now = %s < %s < %s", window_start, cron_time, now)
    return (launch_time < window_start <= cron_time <= now)

if __name__ == "__main__":

    now = datetime.datetime.now(pytz.utc)

    parser = argparse.ArgumentParser(description='Automatically stop and start ec2 instances based on tags.', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-l", "--loglevel", help="Set logging level", type=str.lower,
                        choices=['debug', 'info', 'warning', 'error', 'critical'])
    parser.add_argument("-f", "--logfile", help="Enable logging to filename")
    parser.add_argument("-m", "--logmax", help="Maximum log size before rotation in megabytes", default=1, type=int)
    parser.add_argument("-b", "--logbackups", help="Maximum number of rotated logs to keep", default=10, type=int)
    parser.add_argument("-s", "--startwin", help="How many minutes early an instance may be started", default=start_window_size_minutes, type=int)
    parser.add_argument("-t", "--stopwin", help="How many minutes after an instance will be stopped", default=stop_window_size_minutes, type=int)
    parser.add_argument("-n", "--dry-run", help="trial run with no instance stops or starts", action="store_true")
    args = parser.parse_args()

    if args.loglevel:
        log_level = getattr(logging, args.loglevel.upper(), None)
    else:
        log_level = logging.INFO

    log_format = "%(asctime)s %(levelname)s %(message)s"

    if args.logfile:
        file_handler = logging.handlers.RotatingFileHandler(filename=args.logfile, maxBytes=args.logmax * 1024 * 1024, backupCount=args.logbackups)
        file_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_handler)
    else:
        logging.basicConfig(format=log_format)

    logger.setLevel(log_level)

    logger.info("Run starting.")

    # go through all regions
    instances = 0
    for region in boto.ec2.regions():
        if region.name not in ['cn-north-1', 'us-gov-west-1']:
            try:
                logger.debug("Connecting to region: %s", region.name)
                conn = boto.ec2.connect_to_region(region.name)
                reservations = conn.get_all_instances()
                start_list = []
                stop_list = []
                slept = False
                for reservation in reservations:
                    for instance in reservation.instances:
                        instances += 1
                        name = instance.tags['Name'] if 'Name' in instance.tags else 'Unknown'
                        state = instance.state

                        # check auto:start and auto:stop tags
                        start_sched = instance.tags['auto:start'] if 'auto:start' in instance.tags else None
                        stop_sched = instance.tags['auto:stop'] if 'auto:stop' in instance.tags else None

                        launch_time = dateutil.parser.parse(instance.launch_time)

                        logger.debug("region: %s name: %s  id: %s launch: %s state: %s start_sched: %s stop_sched: %s",
                                     region.name, name, instance.id, instance.launch_time, state, start_sched, stop_sched)

                        try:
                            # queue up instances that have the start time falls between now and the next 30 minutes
                            if start_sched and state == "stopped" and time_to_start(start_sched, now):
                                logger.info("Starting instance: %s (%s)", name, instance.id)
                                start_list.append(instance.id)
                        except (ValueError, KeyError) as ve:
                            logger.error("Invalid auto:start tag on instance %s (%s): '%s' (%s)", name, instance.id, start_sched, ve)

                        try:
                            # queue up instances that have the stop time falls between 30 minutes ago and now
                            if stop_sched and state == "running" and time_to_stop(stop_sched, now, launch_time):
                                logger.info("Stopping instance: %s (%s)", name, instance.id)
                                stop_list.append(instance.id)
                        except (ValueError, KeyError) as ve:
                            logger.error("Invalid auto:stop tag on instance %s (%s): '%s' (%s)", name, instance.id, stop_sched, ve)

                # start instances
                if start_list and not args.dry_run:
                    ret = conn.start_instances(instance_ids=start_list, dry_run=False)
                    logger.info("start_instances %s", ret)

                    # Check for any ELBs that need to be updated
                    elb_conn = boto.ec2.elb.connect_to_region(region.name)
                    load_balancers = elb_conn.get_all_load_balancers()
                    for load_balancer in load_balancers:
                        for elb_instance in load_balancer.instances:
                            if elb_instance.id in start_list:
                                if (not slept):
                                    # Sleep to increase chances of instances properly re-registering with ELB
                                    sleep(5)
                                    slept = True
                                logger.info("Re-registering instance %s in elastic load balancer %s", elb_instance.id, load_balancer.name)
                                load_balancer.deregister_instances([elb_instance.id])
                                load_balancer.register_instances([elb_instance.id])

                # stop instances
                if stop_list and not args.dry_run:
                    ret = conn.stop_instances(instance_ids=stop_list, dry_run=False)
                    logger.info("stop_instances %s", ret)

            except Exception as e:
                logger.error("Exception error in %s: %s", region.name, e)

    logger.info("Run complete with %d instances evaluated.", instances)