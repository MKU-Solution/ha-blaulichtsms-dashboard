"""Konstanten für die BlaulichtSMS Dashboard Integration."""
import aiohttp

DOMAIN = "blaulichtsms_dashboard"

CONF_CUSTOMER_ID = "customer_id"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 3600

BASE_URL = "https://api.blaulichtsms.net/blaulicht/api/alarm/v1/dashboard"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)

# Ein Alarm gilt so lange als aktiv.
ALARM_ACTIVE_DURATION_HOURS = 1
