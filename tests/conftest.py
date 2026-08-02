"""Shared test data for the BlaulichtSMS Dashboard tests.

Die HA-abhängigen Tests fordern die Fixture ``enable_custom_integrations``
explizit an - so bleiben die reinen Unit-Tests in ``test_helpers.py`` auch ohne
das ``pytest-homeassistant-custom-component``-Plugin lauffähig (z.B. unter
Windows, wo Home Assistant selbst nicht importierbar ist).
"""
from custom_components.blaulichtsms_dashboard.const import (
    CONF_CUSTOMER_ID,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)

MOCK_CONFIG = {
    CONF_CUSTOMER_ID: "12345",
    CONF_USERNAME: "monitor",
    CONF_PASSWORD: "geheim",
    CONF_SCAN_INTERVAL: 30,
}
