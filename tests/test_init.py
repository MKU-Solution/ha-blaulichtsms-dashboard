"""Tests for the coordinator and the config entry migration."""
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.blaulichtsms_dashboard import (
    BlaulichtSMSCoordinator,
    BlaulichtSMSSessionExpired,
)
from custom_components.blaulichtsms_dashboard.const import BASE_URL, DOMAIN

from .conftest import MOCK_CONFIG

LOGIN_URL = f"{BASE_URL}/login"


def _entry(hass, **kwargs):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="12345_monitor",
        version=kwargs.pop("version", 2),
        **kwargs,
    )
    entry.add_to_hass(hass)
    return entry


async def test_setup_and_unload(hass, enable_custom_integrations, aioclient_mock):
    """Happy path: Login, Abruf, Entladen."""
    aioclient_mock.post(LOGIN_URL, json={"sessionId": "session-1"})
    aioclient_mock.get(f"{BASE_URL}/session-1", json={"alarms": []})

    entry = _entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_invalid_credentials_start_reauth(
    hass, enable_custom_integrations, aioclient_mock
):
    """Regression A2: falsche Zugangsdaten müssen den Reauth-Flow auslösen."""
    aioclient_mock.post(LOGIN_URL, status=401)

    entry = _entry(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow for flow in flows if flow["context"]["source"] == "reauth"]


async def test_alarms_are_sorted_newest_first(
    hass, enable_custom_integrations, aioclient_mock
):
    """Alle Sensoren lesen data[0] - die Reihenfolge darf nicht von der API abhängen."""
    aioclient_mock.post(LOGIN_URL, json={"sessionId": "session-1"})
    aioclient_mock.get(
        f"{BASE_URL}/session-1",
        json={
            "alarms": [
                {"alarmDate": "2026-08-01T10:00:00Z", "alarmText": "alt"},
                {"alarmDate": "2026-08-01T12:00:00Z", "alarmText": "neu"},
            ]
        },
    )

    entry = _entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert [alarm["alarmText"] for alarm in coordinator.data] == ["neu", "alt"]


class TestUpdateDataErrorHandling:
    """Direkte Tests der Retry-Logik in _async_update_data (Regression A2)."""

    @staticmethod
    def _coordinator(hass):
        entry = _entry(hass)
        return BlaulichtSMSCoordinator(hass, entry)

    async def test_expired_session_triggers_relogin(self, hass, enable_custom_integrations):
        coordinator = self._coordinator(hass)
        coordinator.blaulicht_session_id = "abgelaufen"
        calls = []

        async def fake_login():
            calls.append("login")
            coordinator.blaulicht_session_id = "frisch"

        async def fake_fetch():
            calls.append("fetch")
            if coordinator.blaulicht_session_id == "abgelaufen":
                raise BlaulichtSMSSessionExpired
            return [{"alarmText": "ok"}]

        coordinator._login = fake_login
        coordinator._fetch_alarms = fake_fetch

        assert await coordinator._async_update_data() == [{"alarmText": "ok"}]
        assert calls == ["fetch", "login", "fetch"]

    async def test_session_rejected_after_relogin_raises_auth_failed(
        self, hass, enable_custom_integrations
    ):
        coordinator = self._coordinator(hass)
        coordinator.blaulicht_session_id = "abgelaufen"

        async def fake_login():
            return None

        async def fake_fetch():
            raise BlaulichtSMSSessionExpired

        coordinator._login = fake_login
        coordinator._fetch_alarms = fake_fetch

        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()

    async def test_auth_failure_is_not_swallowed(self, hass, enable_custom_integrations):
        """Der alte Code hat ConfigEntryAuthFailed in UpdateFailed umgewandelt."""
        coordinator = self._coordinator(hass)
        login_calls = []

        async def fake_login():
            login_calls.append(1)
            raise ConfigEntryAuthFailed("Ungültige Zugangsdaten")

        coordinator._login = fake_login

        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()
        assert len(login_calls) == 1


async def test_migration_from_v1_rewrites_ids(
    hass, enable_custom_integrations, aioclient_mock
):
    """Bestehende Installationen behalten ihre entity_ids."""
    aioclient_mock.post(LOGIN_URL, json={"sessionId": "session-1"})
    aioclient_mock.get(f"{BASE_URL}/session-1", json={"alarms": []})

    entry = _entry(hass, version=1)

    ent_reg = er.async_get(hass)
    old_entity = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        "blaulichtsms_12345_alarm_text",
        config_entry=entry,
        suggested_object_id="blaulichtsms_alarm_text",
    )
    dev_reg = dr.async_get(hass)
    device_entry = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "12345")},
        name="BlaulichtSMS (monitor)",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2

    migrated = ent_reg.async_get(old_entity.entity_id)
    assert migrated is not None
    assert migrated.unique_id == f"{entry.entry_id}_alarm_text"

    assert dev_reg.async_get(device_entry.id).identifiers == {(DOMAIN, entry.entry_id)}
