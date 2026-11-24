"""Log alert event names must match the filters that alert on them.

A Cloud Monitoring alert matches ``jsonPayload.monitor_event`` on a log line.
The name is written once where the line is logged and once in a filter, so a
rename on either side would leave the alert silently matching nothing.
"""

import json
import logging
import re
import unittest
from pathlib import Path

from backend.common.logger import CloudJsonFormatter
from backend.common.monitor_events import CRON_EVENTS, MonitorEvent

# Runfiles paths, relative to the repository root (see //:monitor_event_consumers).
_MONITORING_TF = Path("terraform/modules/purrf_instance/monitoring.tf")
_CRONJOBS_YAML = Path("helm/purrf/templates/cronjobs.yaml")

# In HCL the filter reads jsonPayload.monitor_event=\"<name>\".
_TF_EVENT = re.compile(r'monitor_event=\\"([^"\\]+)\\"')
# The cron script prints JSON with "monitor_event":"<name>".
_HELM_EVENT = re.compile(r'"monitor_event":"([^"]+)"')


class MonitorEventsTest(unittest.TestCase):
    def test_every_event_monitoring_matches_is_defined(self):
        matched = set(_TF_EVENT.findall(_MONITORING_TF.read_text()))

        self.assertTrue(matched, "found no monitor_event filters; did the file move?")
        self.assertLessEqual(matched, {str(event) for event in MonitorEvent})

    def test_the_cron_script_prints_exactly_the_cron_events(self):
        printed = set(_HELM_EVENT.findall(_CRONJOBS_YAML.read_text()))

        self.assertEqual(printed, {str(event) for event in CRON_EVENTS})

    def test_every_backend_event_is_matched_by_monitoring(self):
        """An event the backend logs but nothing matches alerts no one."""
        matched = set(_TF_EVENT.findall(_MONITORING_TF.read_text()))
        backend_events = {str(event) for event in MonitorEvent} - {
            str(event) for event in CRON_EVENTS
        }

        self.assertLessEqual(backend_events, matched)

    def test_a_logged_event_is_written_as_its_plain_name(self):
        """The filter compares strings; an enum repr would never match."""
        record = logging.LogRecord("backend.x", logging.WARNING, "", 0, "m", (), None)
        record.monitor_event = MonitorEvent.CHAT_SUBSCRIPTION_STATUS

        line = json.loads(CloudJsonFormatter("%(message)s").format(record))

        self.assertEqual(line["monitor_event"], "subscription.status")


if __name__ == "__main__":
    unittest.main()
