EC2 Operator
============

Automatically starts and stops Amazon EC2 instances based on auto:start and auto:stop tags in cron format. Designed to
run simply without excessive configuration, all options can be configured via command line or instance tags.

It will also check elastic load balancers when starting instances and de-register then re-register the instance against
any load balancers to make sure that the instances comes online in the elastic load balancer in a reasonable time frame.

Example
-------

Start an instance at 15:00 UTC Monday through Friday and stop it at 04:00 UTC every day.

**auto:start** 0 15 * * 1-5
**auto:stop**  0 4 * * *

Usage
-----

    usage: ec2_operator.py [-h] [-l {debug,info,warning,error,critical}]
                           [-f LOGFILE] [-m LOGMAX] [-b LOGBACKUPS] [-s STARTWIN]
                           [-t STOPWIN] [-n]

    Automatically stop and start ec2 instances based on tags.

    optional arguments:
      -h, --help            show this help message and exit
      -l {debug,info,warning,error,critical}, --loglevel {debug,info,warning,error,critical}
                            Set logging level (default: None)
      -f LOGFILE, --logfile LOGFILE
                            Enable logging to filename (default: None)
      -m LOGMAX, --logmax LOGMAX
                            Maximum log size before rotation in megabytes
                            (default: 1)
      -b LOGBACKUPS, --logbackups LOGBACKUPS
                            Maximum number of rotated logs to keep (default: 10)
      -s STARTWIN, --startwin STARTWIN
                            How many minutes early an instance may be started
                            (default: 10)
      -t STOPWIN, --stopwin STOPWIN
                            How many minutes after an instance will be stopped
                            (default: 60)
      -n, --dry-run         trial run with no instance stops or starts (default:
                            False)

Example
--------

ec2_operator.py -l debug -f /var/log/ec2_operator.log -m 5 -b 10 -s 5 -t 30

Runs with debug level log output to /var/log/ec2_operator. Log files are rotated at 5 megabytes and up to 10 log
files are kept. Instances will be started if they are scheduled to start within 5 minutes of a run. They will be
stopped if the they are found running within 60 minutes of a run.

An instance will not be restarted if its launch time is after the beginning of the shutdown window. For example, if
the shutdown window is 01:00 and someone restarted the instance at 01:05, a run at 01:10 would not start that instance
back up.

The stop window is 60 minutes by default to give ample room to make sure the instance is shut down.

The start window is 10 minutes in order to give several chances to start the instance if run on a */5 schedule as well
as to give the instance plenty of time to start up before it is needed.


Scheduling
----------

This is typically executed via cron. The interval needs to make sense according to the start and stop windows used.
Running every 5 minutes with the default windows is the normal use case.

    */5 * * * * /usr/local/bin/ec2_operator.py --loglevel info --logfile /var/log/ec2-operator/ec2-operator.log


Permissions
-----------

Requires either an instance role or AWS credentials configured with the following permissions:

    {
       "Statement":[
          {
             "Action":[
                "ec2:DescribeInstances",
                "ec2:StartInstances",
                "ec2:StopInstances",
                "elasticloadbalancing:DeregisterInstancesFromLoadBalancer",
                "elasticloadbalancing:DescribeLoadBalancerAttributes",
                "elasticloadbalancing:DescribeLoadBalancers",
                "elasticloadbalancing:RegisterInstancesWithLoadBalancer"
             ],
             "Effect":"Allow",
             "Resource":"*"
          }
       ]
    }