#!/usr/bin/python

import boto.ec2
import croniter
import datetime

# return true if the cron schedule falls between now and now+seconds
def time_to_action(sched, now, seconds):
  try:
    cron = croniter.croniter(sched, now)
    d1 = now + datetime.timedelta(0, seconds)
    if (seconds > 0):
      d2 = cron.get_next(datetime.datetime)
      ret = (now < d2 and d2 < d1)
    else:
      d2 = cron.get_prev(datetime.datetime)
      ret = (d1 < d2 and d2 < now)
    print "now %s" % now
    print "d1 %s" % d1
    print "d2 %s" % d2
  except:
    ret = False
  print "time_to_action %s" % ret
  return ret

now = datetime.datetime.now()

# go through all regions
for region in boto.ec2.regions():
  try:
    conn=boto.ec2.connect_to_region(region.name)
    reservations = conn.get_all_instances()
    start_list = []
    stop_list = []
    for res in reservations:
      for inst in res.instances:
        name = inst.tags['Name'] if 'Name' in inst.tags else 'Unknown'
        state = inst.state

        # check auto:start and auto:stop tags
        start_sched = inst.tags['auto:start'] if 'auto:start' in inst.tags else None
        stop_sched = inst.tags['auto:stop'] if 'auto:stop' in inst.tags else None

        print "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s" % (region.name, name, inst.id, inst.instance_type, inst.launch_time, state, start_sched, stop_sched, inst.tags)

        # queue up instances that have the start time falls between now and the next 30 minutes
        if start_sched != None and state == "stopped" and time_to_action(start_sched, now, 31 * 60):
          start_list.append(inst.id)

        # queue up instances that have the stop time falls between 30 minutes ago and now
        if stop_sched != None and state == "running" and time_to_action(stop_sched, now, 31 * -60):
          stop_list.append(inst.id)

    # start instances
    if len(start_list) > 0:
      ret = conn.start_instances(instance_ids=start_list, dry_run=False)
      print "start_instances %s" % ret

    # stop instances
    if len(stop_list) > 0:
      ret = conn.stop_instances(instance_ids=stop_list, dry_run=False)
      print "stop_instances %s" % ret

  # most likely will get exception on new beta region and gov cloud
  except Exception as e:
    print 'Exception error in %s: %s' % (region.name, e.message)
