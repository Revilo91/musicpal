# MusicPal Home Assistant Integration - Deutsche Anleitung

Diese Home Assistant Integration ermöglicht die Steuerung Ihres Freecom MusicPal Internet-Radio-Geräts.

## Installation über HACS (Empfohlen)

1. Öffnen Sie HACS in Home Assistant
2. Gehen Sie zu "Integrationen"
3. Klicken Sie auf die drei Punkte oben rechts
4. Wählen Sie "Benutzerdefinierte Repositorys"
5. Fügen Sie diese Repository-URL hinzu: `https://github.com/Revilo91/musicpal`
6. Kategorie auswählen: "Integration"
7. Klicken Sie auf "Hinzufügen"
8. Suchen Sie "MusicPal" in der Integrationsliste und klicken Sie auf "Herunterladen"
9. Starten Sie Home Assistant neu

## Konfiguration

1. Gehen Sie zu Einstellungen → Geräte & Dienste
2. Klicken Sie auf "+ Integration hinzufügen"
3. Suchen Sie nach "MusicPal"
4. Geben Sie Ihre Gerätedetails ein:
   - **Hostname oder IP-Adresse**: Die IP-Adresse oder der Hostname Ihres MusicPal-Geräts
   - **Benutzername**: Standard ist "admin"
   - **Passwort**: Standard ist "admin"
5. Klicken Sie auf "Senden"

### Optionen

Über die Schaltfläche **Konfigurieren** auf der Integrationskarte lässt sich
das Abfrageintervall einstellen (5-300 Sekunden, Standard 30). Der MusicPal
ist Hardware von 2007 - kleinere Werte lassen Home Assistant schneller
reagieren, belasten das Gerät aber stärker.

## Funktionen

### Media Player Entität

Die Integration erstellt eine Media-Player-Entität mit folgenden Funktionen:

- **Stromsteuerung**: Gerät ein-/ausschalten
- **Wiedergabesteuerung**: Abspielen, Pausieren, nächster Titel
- **Lautstärkeregelung**: Lautstärke einstellen (0-100%) oder Lautstärke hoch/runter
- **Quellenauswahl**: Aus konfigurierten Favoriten auswählen
- **Medien abspielen**: Eine Medien-URL direkt abspielen

### Sensor-Entitäten

Drei Sensor-Entitäten werden erstellt:

1. **Anzeige**: Der aktuell auf dem Gerätedisplay dargestellte Text
2. **Letzter Start**: Zeitpunkt des letzten Gerätestarts (ein stabiler
   Zeitstempel statt eines stetig wachsenden Zählers, damit die
   Recorder-Datenbank nicht unnötig wächst)
3. **Favoriten**: Anzahl der konfigurierten Favoriten; die Namen stehen im
   Attribut `favorites`

Alle drei sind als Diagnose-Entitäten gekennzeichnet.

### Dienste

#### `musicpal.show_message`

Eine benutzerdefinierte Nachricht auf dem MusicPal-Bildschirm anzeigen.

```yaml
action: musicpal.show_message
target:
  entity_id: media_player.musicpal
data:
  message: "Hallo von Home Assistant!"
```

#### `musicpal.show_clock`

Die Uhr auf dem MusicPal-Bildschirm anzeigen.

```yaml
action: musicpal.show_clock
target:
  entity_id: media_player.musicpal
```

#### `musicpal.reboot`

Das MusicPal-Gerät neu starten.

```yaml
action: musicpal.reboot
target:
  entity_id: media_player.musicpal
```

## Beispiel-Automatisierungen

### Favorit zu einer bestimmten Zeit abspielen

```yaml
automation:
  - alias: "Morgenradio"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - action: media_player.select_source
        target:
          entity_id: media_player.musicpal
        data:
          source: "Morgen Radio"
```

### Nachricht auf MusicPal-Display anzeigen

```yaml
automation:
  - alias: "Türklingel Benachrichtigung"
    trigger:
      - platform: state
        entity_id: binary_sensor.doorbell
        to: "on"
    action:
      - action: musicpal.show_message
        target:
          entity_id: media_player.musicpal
        data:
          message: "Jemand an der Tür!"
```

## Anforderungen

- Home Assistant 2024.12.0 oder neuer
- Ein Freecom MusicPal-Gerät in Ihrem Netzwerk

## Fehlerbehebung

### Keine Verbindung zum Gerät möglich

- Stellen Sie sicher, dass das MusicPal-Gerät eingeschaltet und mit Ihrem Netzwerk verbunden ist
- Überprüfen Sie, ob die IP-Adresse oder der Hostname korrekt ist
- Prüfen Sie, ob Sie das Gerät von Ihrem Home Assistant Host aus anpingen können
- Stellen Sie sicher, dass Benutzername und Passwort korrekt sind (Standard: admin/admin)

## Unterstützung

Bei Problemen oder Feature-Anfragen besuchen Sie bitte das [GitHub Repository](https://github.com/Revilo91/musicpal/issues).

## Lizenz

Dieses Projekt ist unter der GNU General Public License v3 (GPLv3) lizenziert.

## Credits

Basierend auf dem ursprünglichen `musicpal` CLI-Tool von Joerg Mechnich.
