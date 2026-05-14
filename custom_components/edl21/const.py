"""Constants for the EDL21 component."""

from __future__ import annotations

import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "edl21"

# Config-entry data
CONF_SERIAL_PORT = "serial_port"

# Options
CONF_SCAN_INTERVAL = "scan_interval_seconds"

# Scan-interval bounds and default.
#
# Upstream hard-codes a 60 s entity-update throttle. The smart meter
# usually emits one telegram per second; meaningful values for the
# update throttle range from 1 s (push every telegram) to several
# minutes. 10 s matches the fuslwusl fork's default and is a good
# compromise between detail and history-table size.
DEFAULT_SCAN_INTERVAL = 10
MIN_SCAN_INTERVAL = 1
MAX_SCAN_INTERVAL = 3600

SIGNAL_EDL21_TELEGRAM = "edl21_telegram"

DEFAULT_TITLE = "Smart Meter"

DEFAULT_DEVICE_NAME = "Smart Meter"
