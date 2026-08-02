"""Tests for the BlaulichtSMS Dashboard config flow."""
from unittest.mock import patch

import aiohttp
import pytest
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.blaulichtsms_dashboard.const import (
    BASE_URL,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)

from .conftest import MOCK_CONFIG

LOGIN_URL = f"{BASE_URL}/login"
SETUP_TARGET = "custom_components.blaulichtsms_dashboard.async_setup_entry"


async def test_user_flow_success(hass, enable_custom_integrations, aioclient_mock):
    """A valid login creates the entry with a stable unique_id."""
    aioclient_mock.post(LOGIN_URL, json={"sessionId": "session-1"})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(SETUP_TARGET, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], dict(MOCK_CONFIG)
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "BlaulichtSMS (monitor)"
    assert result["data"] == MOCK_CONFIG
    assert result["result"].unique_id == "12345_monitor"
    assert result["result"].version == 2


@pytest.mark.parametrize(
    ("mock_kwargs", "expected_error"),
    [
        ({"status": 401}, "invalid_auth"),
        ({"status": 403}, "invalid_auth"),
        # Login ohne Session-ID ist genauso wertlos wie ein 401.
        ({"json": {}}, "invalid_auth"),
        ({"exc": aiohttp.ClientError()}, "cannot_connect"),
    ],
)
async def test_user_flow_errors(
    hass, enable_custom_integrations, aioclient_mock, mock_kwargs, expected_error
):
    """Login-Fehler landen als Formularfehler, nicht als stiller Eintrag."""
    aioclient_mock.post(LOGIN_URL, **mock_kwargs)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(MOCK_CONFIG)
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_user_flow_recovers_after_error(
    hass, enable_custom_integrations, aioclient_mock
):
    """Nach einem Fehlversuch kann der Nutzer es direkt erneut probieren."""
    aioclient_mock.post(LOGIN_URL, status=401)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(MOCK_CONFIG)
    )
    assert result["errors"] == {"base": "invalid_auth"}

    aioclient_mock.clear_requests()
    aioclient_mock.post(LOGIN_URL, json={"sessionId": "session-1"})

    with patch(SETUP_TARGET, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], dict(MOCK_CONFIG)
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_aborts_when_already_configured(
    hass, enable_custom_integrations, aioclient_mock
):
    """Derselbe Account darf nicht zweimal angelegt werden."""
    MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id="12345_monitor", version=2
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(MOCK_CONFIG)
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("interval", [0, -5, 100000])
async def test_scan_interval_is_rejected(
    hass, enable_custom_integrations, interval
):
    """Ein Intervall von 0 würde die API im Dauerlauf abfragen."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with pytest.raises((InvalidData, vol.Invalid)):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {**MOCK_CONFIG, CONF_SCAN_INTERVAL: interval}
        )


async def test_reauth_flow(hass, enable_custom_integrations, aioclient_mock):
    """Ein neues Passwort wird geprüft und in den Eintrag geschrieben."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id="12345_monitor", version=2
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    aioclient_mock.post(LOGIN_URL, json={"sessionId": "session-neu"})
    with patch(SETUP_TARGET, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "neues-passwort"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "neues-passwort"


async def test_reauth_flow_rejects_wrong_password(
    hass, enable_custom_integrations, aioclient_mock
):
    """Ein weiterhin falsches Passwort wird nicht gespeichert."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id="12345_monitor", version=2
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    aioclient_mock.post(LOGIN_URL, status=401)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "immer-noch-falsch"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_PASSWORD] == MOCK_CONFIG[CONF_PASSWORD]


async def test_options_flow_updates_interval(
    hass, enable_custom_integrations, aioclient_mock
):
    """Das Polling-Intervall lässt sich nachträglich ändern."""
    aioclient_mock.post(LOGIN_URL, json={"sessionId": "session-1"})
    aioclient_mock.get(f"{BASE_URL}/session-1", json={"alarms": []})

    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id="12345_monitor", version=2
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 60}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == 60
