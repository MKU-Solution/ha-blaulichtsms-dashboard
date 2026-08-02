<p align="center">
  <img src="https://raw.githubusercontent.com/seipekm/ha-blaulichtsms-dashboard/main/logo.png" alt="BlaulichtSMS Dashboard Logo" width="200">
</p>

# BlaulichtSMS Dashboard für Home Assistant

Eine Home Assistant Custom Component, um aktive Einsatzalarme von [BlaulichtSMS](https://blaulichtsms.net/) abzufragen und darzustellen.

## Eigenschaften
- Fragt die BlaulichtSMS Dashboard API ab.
- Asynchrones Polling.
- Eigener Sensor mit Einsatzdetails (Ort, alarmierte Gruppen, Anzahl Zugesagt/Abgesagt).
- Binary Sensor **Einsatz Aktiv** als sprachneutraler Auslöser für Automatisierungen.
- Aufbereiteter **TTS Text** für Sprachdurchsagen.
- Einfache Einrichtung über die Home Assistant Benutzeroberfläche, inkl. Prüfung der Zugangsdaten.

## Voraussetzungen

Bevor du diese Integration nutzen kannst, musst du zwingend ein **Dashboard (Einsatzmonitor)** in BlaulichtSMS angelegt haben. Die Integration loggt sich in dieses Dashboard ein, um die Daten abzurufen.

1. Logge dich unter [start.blaulichtsms.net](https://start.blaulichtsms.net) in die Web-Plattform ein.
2. Gehe im Menü auf **Einsatzmonitor** -> **Anzeige & Konfiguration**.
3. Klicke auf **Neuen Einsatzmonitor anlegen**.
4. Vergib einen Namen und ein Passwort.
*(Genau diese speziellen Dashboard-Zugangsdaten benötigst du später für die Einrichtung in Home Assistant!)*
## Installation via HACS (Empfohlen)

1. Öffne **HACS** in deiner Home Assistant Instanz.
2. Klicke auf **Integrationen**.
3. Klicke oben rechts auf das Drei-Punkte-Menü und wähle **Benutzerdefinierte Repositories**.
4. Füge die URL dieses GitHub Repositories ein.
5. Wähle als Kategorie **Integration**.
6. Klicke auf Hinzufügen.
7. Suche nun in HACS nach "BlaulichtSMS Dashboard" und klicke auf "Herunterladen".
8. Starte Home Assistant neu.
9. Gehe zu **Einstellungen -> Geräte & Dienste -> Integration hinzufügen**, suche nach "BlaulichtSMS Dashboard" und gib deine Zugangsdaten ein.

## Manuelle Installation

1. Lade dir dieses Repository als ZIP herunter.
2. Entpacke den Ordner `custom_components/blaulichtsms_dashboard` in dein Home Assistant `custom_components` Verzeichnis.
3. Starte Home Assistant neu.
4. Richte die Integration über **Einstellungen -> Geräte & Dienste** ein.

## Automatisierungs-Beispiel

Sobald ein Einsatz eingeht, schaltet der Binary Sensor **Einsatz Aktiv** auf `on`. Nach einer Stunde ohne neues Alarm-Datum schaltet er automatisch zurück. Diesen Wechsel kannst du optimal als Auslöser (Trigger) für Home Assistant Automatisierungen nutzen. Parallel gibt es weiterhin den Sensor **Einsatzstatus** mit den Werten `Aktiv` / `Inaktiv`.

> **Hinweis zu den Entity-IDs:** die Entities tragen den Namen des Dashboard-Benutzers, heißen also z.B. `binary_sensor.blaulichtsms_monitor_einsatz_aktiv`. Schau die exakten IDs in den Entwicklerwerkzeugen nach und passe die Beispiele unten an.

Hier ist ein Beispiel, wie du bei einem Alarm automatisch das Licht einschaltest und eine Push-Nachricht mit dem Einsatzort auf dein Handy schickst:

```yaml
alias: "Feuerwehr: Neuer Alarm (BlaulichtSMS)"
description: "Wird ausgelöst, wenn ein neuer Alarm über BlaulichtSMS reinkommt."
mode: single

triggers:
  - trigger: state
    entity_id: binary_sensor.blaulichtsms_einsatz_aktiv
    from: "off"
    to: "on"

actions:
  # 1. Licht im Flur einschalten (Beispiel)
  - action: light.turn_on
    target:
      entity_id: light.flur
    data:
      brightness_pct: 100
      color_name: red

  # 2. Eine Push-Benachrichtigung mit allen Infos an dein Handy schicken
  - action: notify.notify
    data:
      title: "🚨 FEUERWEHR EINSATZ 🚨"
      message: >
        Alarmierungs-Text: {{ state_attr('sensor.blaulichtsms_alarm_text', 'full_value') }}

        Einsatzort: {{ states('sensor.blaulichtsms_einsatzort') }}
        Alarmierte Gruppen: {{ states('sensor.blaulichtsms_alarm_gruppen') }}
```

### Lange Alarmtexte

Home Assistant erlaubt für den Zustand einer Entity maximal 255 Zeichen. Längere Alarmtexte werden im Zustand gekürzt (erkennbar am `…` am Ende) — der **vollständige** Text steht immer im Attribut `full_value`:

```jinja
{{ state_attr('sensor.blaulichtsms_alarm_text', 'full_value') }}
```

### Sprachdurchsage (TTS)

Der Sensor **TTS Text** liefert einen vorlesbaren Text, in dem Abkürzungen wie `VU` oder `BMA` ausgeschrieben und Sonderzeichen entfernt sind. Der Knopf **TTS Wiederholen** feuert zusätzlich das Event `blaulichtsms_dashboard_repeat_tts` mit dem Text im Payload:

```yaml
triggers:
  - trigger: event
    event_type: blaulichtsms_dashboard_repeat_tts

actions:
  - action: tts.speak
    target:
      entity_id: tts.piper
    data:
      media_player_entity_id: media_player.wohnzimmer
      message: "{{ trigger.event.data.tts_text }}"
```
