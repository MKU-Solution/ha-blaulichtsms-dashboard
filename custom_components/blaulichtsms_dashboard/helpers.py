"""Reine Hilfsfunktionen für die BlaulichtSMS Dashboard Integration.

Bewusst ohne Home-Assistant-Abhängigkeiten (außer Konstanten), damit sie sich
direkt unit-testen lassen.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.const import MAX_LENGTH_STATE_STATE

from .const import ALARM_ACTIVE_DURATION_HOURS

TTS_REPLACEMENTS = {
    r"\bVU\b": "Verkehrsunfall",
    r"\bBMA\b": "Brandmeldeanlage",
    r"\bPKW\b": "Personenkraftwagen",
    r"\bLKW\b": "Lastkraftwagen",
    r"\bRTW\b": "Rettungswagen",
    r"\bNEF\b": "Notarzteinsatzfahrzeug",
    r"\bFF\b": "Freiwillige Feuerwehr",
    r"\bBF\b": "Berufsfeuerwehr",
}


def is_alarm_active(data) -> bool:
    """Check if the latest alarm is active (younger than 1 hour)."""
    if not data:
        return False

    alarm_date_str = data[0].get("alarmDate")
    if not alarm_date_str:
        return True

    try:
        alarm_date = datetime.fromisoformat(alarm_date_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if now - alarm_date > timedelta(hours=ALARM_ACTIVE_DURATION_HOURS):
            return False
        return True
    except Exception:
        return True


def clean_for_tts(text: str) -> str:
    """Prepare text for Text-to-Speech."""
    if not text:
        return ""

    # Alarmcodes sind immer in Großbuchstaben - ohne IGNORECASE, sonst würden
    # kleingeschriebene Wörter im Fließtext ("ff", "vu") fälschlich ersetzt.
    for pattern, replacement in TTS_REPLACEMENTS.items():
        text = re.sub(pattern, replacement, text)

    # Remove special characters
    text = re.sub(r"[-/*_~#|+]", " ", text)

    # Cleanup spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def generate_tts_text(data) -> str:
    """Generate a TTS friendly text."""
    if not is_alarm_active(data):
        return "Kein aktiver Alarm"

    raw_text = data[0].get("alarmText", "")
    alarm_text = clean_for_tts(raw_text)

    is_probe = "probe" in raw_text.lower() or data[0].get("isTestAlarm", False)

    if is_probe:
        return f"Achtung, dies ist ein Probealarm! {alarm_text}"
    else:
        return f"Achtung, Einsatzalarm! {alarm_text}"


def truncate_state(value: Any) -> Any:
    """Shorten a string so Home Assistant accepts it as a state.

    HA verwirft States über MAX_LENGTH_STATE_STATE Zeichen. Echte Einsatztexte
    überschreiten das regelmäßig - der ungekürzte Wert steht im Attribut
    ``full_value`` zur Verfügung.
    """
    if isinstance(value, str) and len(value) > MAX_LENGTH_STATE_STATE:
        return value[: MAX_LENGTH_STATE_STATE - 1] + "…"
    return value
