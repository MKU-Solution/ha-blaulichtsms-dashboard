"""Tests for the pure helper functions."""
from datetime import datetime, timedelta, timezone

import pytest
from homeassistant.const import MAX_LENGTH_STATE_STATE

from custom_components.blaulichtsms_dashboard.helpers import (
    clean_for_tts,
    generate_tts_text,
    is_alarm_active,
    truncate_state,
)


def _alarm(minutes_ago: float = 0, **extra):
    """Build an alarm dict with a timestamp relative to now."""
    stamp = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return {"alarmDate": stamp.isoformat().replace("+00:00", "Z"), **extra}


class TestIsAlarmActive:
    def test_no_data(self):
        assert is_alarm_active([]) is False
        assert is_alarm_active(None) is False

    def test_recent_alarm(self):
        assert is_alarm_active([_alarm(minutes_ago=10)]) is True

    def test_old_alarm(self):
        assert is_alarm_active([_alarm(minutes_ago=120)]) is False

    def test_just_inside_the_window(self):
        assert is_alarm_active([_alarm(minutes_ago=59)]) is True

    def test_just_outside_the_window(self):
        assert is_alarm_active([_alarm(minutes_ago=61)]) is False

    def test_missing_date_is_treated_as_active(self):
        assert is_alarm_active([{"alarmText": "Brand"}]) is True

    def test_unparsable_date_is_treated_as_active(self):
        assert is_alarm_active([{"alarmDate": "irgendwas"}]) is True


class TestCleanForTts:
    def test_empty(self):
        assert clean_for_tts("") == ""
        assert clean_for_tts(None) == ""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("VU auf der A1", "Verkehrsunfall auf der A1"),
            ("BMA ausgelöst", "Brandmeldeanlage ausgelöst"),
            ("PKW gegen LKW", "Personenkraftwagen gegen Lastkraftwagen"),
            ("RTW und NEF", "Rettungswagen und Notarzteinsatzfahrzeug"),
            ("FF Musterdorf", "Freiwillige Feuerwehr Musterdorf"),
        ],
    )
    def test_abbreviations(self, raw, expected):
        assert clean_for_tts(raw) == expected

    def test_lowercase_words_are_not_replaced(self):
        """Ohne IGNORECASE bleibt Fließtext unangetastet (Regression A5)."""
        assert clean_for_tts("Er lief zum Ff und schaute") == "Er lief zum Ff und schaute"
        assert clean_for_tts("das vu war klein") == "das vu war klein"

    def test_alarm_codes_stay_untouched(self):
        assert clean_for_tts("B2 Zimmerbrand") == "B2 Zimmerbrand"
        assert clean_for_tts("T1 Technischer Einsatz") == "T1 Technischer Einsatz"

    def test_special_characters_and_spaces(self):
        assert clean_for_tts("Brand -  Haus/Garage  #3") == "Brand Haus Garage 3"


class TestGenerateTtsText:
    def test_no_active_alarm(self):
        assert generate_tts_text([]) == "Kein aktiver Alarm"
        assert generate_tts_text([_alarm(minutes_ago=120)]) == "Kein aktiver Alarm"

    def test_real_alarm(self):
        data = [_alarm(alarmText="B2 Zimmerbrand")]
        assert generate_tts_text(data) == "Achtung, Einsatzalarm! B2 Zimmerbrand"

    def test_probe_detected_in_text(self):
        data = [_alarm(alarmText="Probe Alarm Übung")]
        assert generate_tts_text(data).startswith("Achtung, dies ist ein Probealarm!")

    def test_probe_detected_via_flag(self):
        data = [_alarm(alarmText="B2 Zimmerbrand", isTestAlarm=True)]
        assert generate_tts_text(data).startswith("Achtung, dies ist ein Probealarm!")

    def test_abbreviations_are_expanded(self):
        data = [_alarm(alarmText="VU mit PKW")]
        assert generate_tts_text(data) == (
            "Achtung, Einsatzalarm! Verkehrsunfall mit Personenkraftwagen"
        )


class TestTruncateState:
    def test_short_string_unchanged(self):
        assert truncate_state("kurz") == "kurz"

    def test_exactly_at_the_limit_unchanged(self):
        value = "x" * MAX_LENGTH_STATE_STATE
        assert truncate_state(value) == value

    def test_long_string_truncated(self):
        value = "x" * 400
        result = truncate_state(value)
        assert len(result) == MAX_LENGTH_STATE_STATE
        assert result.endswith("…")

    def test_non_strings_pass_through(self):
        assert truncate_state(5) == 5
        assert truncate_state(None) is None
