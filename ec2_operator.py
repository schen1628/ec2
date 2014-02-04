#!/usr/bin/python

import boto.ec2
import croniter
import datetime

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

conn=boto.ec2.connect_to_region('us-east-1')
reservations = conn.get_all_instances()
start_list = []
stop_list = []
for res in reservations:
   for inst in res.instances:
      name = inst.tags['Name'] if 'Name' in inst.tags else 'Unknown'
      start_sched = inst.tags['auto:start'] if 'auto:start' in inst.tags else None
      stop_sched = inst.tags['auto:stop'] if 'auto:stop' in inst.tags else None
      state = inst.state
      print "%s (%s) [%s] [%s] [%s]" % (name, inst.id, state, start_sched, stop_sched)
      if start_sched != None and state == "stopped" and time_to_action(start_sched, now, 31 * 60):
        start_list.append(inst.id)
      if stop_sched != None and state == "running" and time_to_action(stop_sched, now, 31 * -60):
        stop_list.append(inst.id)
if len(start_list) > 0:
   ret = conn.start_instances(instance_ids=start_list, dry_run=False)
   print "start_instances %s" % ret
if len(stop_list) > 0:
   ret = conn.stop_instances(instance_ids=stop_list, dry_run=False)
   print "stop_instances %s" % ret
