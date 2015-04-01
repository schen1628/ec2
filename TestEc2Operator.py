from unittest import TestCase
import ec2_operator
import pytz
from dateutil import parser


class TestEc2Operator(TestCase):
    # croniter requires a tzinfo object that supports localize so simple parsing of the timezone won't work
    def get_pytz_utc_datetime(self, time_string):
        return parser.parse(time_string).replace(tzinfo=pytz.utc)

    def test_bad_cron(self):

        try:
            ec2_operator.time_to_stop("badcron",
                                      self.get_pytz_utc_datetime("Jan 15 2015 00:00"),
                                      self.get_pytz_utc_datetime("Jan 01 2015 00:00"))

        except ValueError:
            pass
        except Exception as e:
            self.fail("Unexpected exception thrown: " + e)
        else:
            self.fail("Expected exception not thrown")

        try:
            ec2_operator.time_to_stop("badcron 0 6 * * *",
                                      self.get_pytz_utc_datetime("Jan 15 2015 00:00"),
                                      self.get_pytz_utc_datetime("Jan 01 2015 00:00"))
        except KeyError:
            pass
        except Exception as e:
            self.fail("Unexpected exception thrown: " + e)
        else:
            self.fail("Expected exception not thrown")

    # Check stop cron time: (window_start <= cron_time <= now)
    def test_time_to_action_stop(self):

        old_launch_time = self.get_pytz_utc_datetime("Jan 01 2012 00:00:00")

        # Stop at 01:00 and it's 00:00 UTC
        self.assertFalse(
            ec2_operator.time_to_stop("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 00:00"), old_launch_time),
            "Stop well before window")

        # Stop at 01:00 and it's 00:59 UTC
        self.assertFalse(
            ec2_operator.time_to_stop("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 00:59"), old_launch_time),
            "Stop one minute before window")

        # Stop at 01:00 and it's 01:00 UTC
        self.assertTrue(
            ec2_operator.time_to_stop("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 01:00"), old_launch_time),
            "Stop at exact window start")

        # Stop at 01:00 and it's 01:00 MST
        self.assertTrue(
            ec2_operator.time_to_stop("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 01:00").replace(
                tzinfo=pytz.timezone('MST')), old_launch_time), "Stop at exact window start MST")

        # Stop at 01:00 and it's 01:01 UTC
        self.assertTrue(
            ec2_operator.time_to_stop("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 01:01"), old_launch_time),
            "Stop one minute inside window")

        # Stop at 01:00 and it's 01:15 UTC
        self.assertTrue(
            ec2_operator.time_to_stop("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 01:15"), old_launch_time),
            "Stop inside window")

        # Stop at 01:00 and it's 01:15 UTC, but the instance was restarted at 00:59 UTC
        self.assertFalse(
            ec2_operator.time_to_stop("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 01:15"),
                                      self.get_pytz_utc_datetime("Jan 15 2015 00:59")),
            "Stop inside window with recent restart #1")

        # Stop at 01:00 and it's 01:15 MST, but the instance was restarted at 00:59 MST
        self.assertFalse(
            ec2_operator.time_to_stop("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 01:15").replace(
                tzinfo=pytz.timezone('MST')),
                self.get_pytz_utc_datetime("Jan 15 2015 00:59").replace(
                tzinfo=pytz.timezone('MST'))), "Stop inside window with recent restart #2")

        # Stop at 01:00 and it's 01:15 UTC, but the instance was restarted at 01:05 UTC
        self.assertFalse(
            ec2_operator.time_to_stop("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 01:15"),
                                      self.get_pytz_utc_datetime("Jan 15 2015 01:05")),
            "Stop inside window with recent restart #3")

        # Stop at 01:00 and it's 01:30 UTC
        self.assertTrue(
            ec2_operator.time_to_stop("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 01:30"), old_launch_time),
            "Stop at exact window end")

        # Stop at 01:00 and it's 02:01 UTC
        self.assertFalse(
            ec2_operator.time_to_stop("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 02:01"), old_launch_time),
            "Stop one minute past window")

        # Stop at 01:00 and it's 05:00 UTC
        self.assertFalse(
            ec2_operator.time_to_stop("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 05:00"), old_launch_time),
            "Stop well past window")

    # Check start cron time: (now <= cron_time <= window_end)
    def test_time_to_action_start(self):
        # Start at 01:00 and it's 00:00 UTC
        self.assertFalse(
            ec2_operator.time_to_start("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 15:00")),
            "Start well before window")

        # Start at 01:00 and it's 00:29 UTC
        self.assertFalse(
            ec2_operator.time_to_start("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 00:29")),
            "Start one minute before window")

        # Start at 01:00 and it's 00:50 UTC
        self.assertTrue(
            ec2_operator.time_to_start("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 00:50")),
            "Start at exact window start")

        # Start at 01:00 and it's 00:51 UTC
        self.assertTrue(
            ec2_operator.time_to_start("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 00:51")),
            "Start one minute inside window")

        # Start at 01:00 and it's 00:55 UTC
        self.assertTrue(
            ec2_operator.time_to_start("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 00:55")),
            "Start inside window")

        # Start at 01:00 and it's 01:00 UTC
        self.assertTrue(
            ec2_operator.time_to_start("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 01:00")),
            "Start at exact window end")

        # Start at 01:00 and it's 01:01 UTC
        self.assertFalse(
            ec2_operator.time_to_start("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 01:01")),
            "Start one minute past window")

        # Start at 01:00 and it's 05:00 UTC
        self.assertFalse(
            ec2_operator.time_to_start("0 1 * * *", self.get_pytz_utc_datetime("Jan 15 2015 05:00")),
            "Start well past window")