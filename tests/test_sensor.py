"""Entity level tests for the BlaulichtSMS Dashboard integration."""
from datetime import datetime, timedelta, timezone

from homeassistant.const import MAX_LENGTH_STATE_STATE, STATE_ON
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.blaulichtsms_dashboard.const import BASE_URL, DOMAIN

from .conftest import MOCK_CONFIG

LOGIN_URL = f"{BASE_URL}/login"
LONG_TEXT = (
    "B2 Zimmerbrand mit Menschenrettung, mehrere Personen im Gebäude gemeldet. "
    * 6
)


def _now_iso() -> str:
    return (
        (datetime.now(timezone.utc) - timedelta(minutes=5))
        .isoformat()
        .replace("+00:00", "Z")
    )


async def _setup(hass, aioclient_mock, alarms):
    aioclient_mock.post(LOGIN_URL, json={"sessionId": "session-1"})
    aioclient_mock.get(f"{BASE_URL}/session-1", json={"alarms": alarms})

    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id="12345_monitor", version=2
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _state(hass, entry, platform: str, key: str):
    """Look the entity up by unique_id - entity_ids hängen an der Sprache."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        platform, DOMAIN, f"{entry.entry_id}_{key}"
    )
    assert entity_id is not None, f"{platform}.{key} wurde nicht angelegt"
    return hass.states.get(entity_id)


async def test_long_alarm_text_is_truncated(
    hass, enable_custom_integrations, aioclient_mock
):
    """Regression A1: HA verwirft States über 255 Zeichen."""
    assert len(LONG_TEXT) > MAX_LENGTH_STATE_STATE

    entry = await _setup(
        hass, aioclient_mock, [{"alarmDate": _now_iso(), "alarmText": LONG_TEXT}]
    )

    state = _state(hass, entry, "sensor", "alarm_text")
    assert len(state.state) == MAX_LENGTH_STATE_STATE
    assert state.state.endswith("…")
    assert state.attributes["full_value"] == LONG_TEXT


async def test_short_text_is_not_truncated(
    hass, enable_custom_integrations, aioclient_mock
):
    entry = await _setup(
        hass, aioclient_mock, [{"alarmDate": _now_iso(), "alarmText": "B2 Zimmerbrand"}]
    )

    state = _state(hass, entry, "sensor", "alarm_text")
    assert state.state == "B2 Zimmerbrand"
    assert state.attributes["full_value"] == "B2 Zimmerbrand"


async def test_alarm_date_is_a_timestamp(
    hass, enable_custom_integrations, aioclient_mock
):
    entry = await _setup(
        hass,
        aioclient_mock,
        [{"alarmDate": "2026-08-01T12:00:00Z", "alarmText": "B2"}],
    )

    state = _state(hass, entry, "sensor", "alarm_date")
    assert state.attributes["device_class"] == "timestamp"
    assert state.state == "2026-08-01T12:00:00+00:00"


async def test_binary_sensor_tracks_active_alarm(
    hass, enable_custom_integrations, aioclient_mock
):
    entry = await _setup(
        hass, aioclient_mock, [{"alarmDate": _now_iso(), "alarmText": "B2"}]
    )

    assert _state(hass, entry, "binary_sensor", "einsatz_aktiv").state == STATE_ON
    assert _state(hass, entry, "sensor", "einsatzstatus").state == "Aktiv"


async def test_no_alarm_states(hass, enable_custom_integrations, aioclient_mock):
    entry = await _setup(hass, aioclient_mock, [])

    assert _state(hass, entry, "sensor", "einsatzstatus").state == "Inaktiv"
    assert _state(hass, entry, "sensor", "aktive_alarme_anzahl").state == "0"
    assert _state(hass, entry, "sensor", "alarm_text").state == "Kein Alarm"
    assert _state(hass, entry, "sensor", "tts_text").state == "Kein aktiver Alarm"
    assert _state(hass, entry, "sensor", "alarm_date").state == "unknown"


async def test_repeat_tts_button_exposes_text(
    hass, enable_custom_integrations, aioclient_mock
):
    entry = await _setup(
        hass,
        aioclient_mock,
        [{"alarmDate": _now_iso(), "alarmText": "VU mit PKW"}],
    )

    state = _state(hass, entry, "button", "repeat_tts_btn")
    assert state.attributes["tts_text"] == (
        "Achtung, Einsatzalarm! Verkehrsunfall mit Personenkraftwagen"
    )
