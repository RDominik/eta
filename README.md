# eta

Kleines PV/Wallbox/Influx-Projekt.

## Setup

1) Python 3.10+ installieren
2) Virtualenv anlegen und aktivieren

```
python3 -m venv .venv
source .venv/bin/activate
```

3) Abhängigkeiten installieren

```
pip install -r requirements.txt
```

4) Konfiguration prüfen/anpassen
- Inverter (Modbus): `src/inverter/readInverter.py` → IP/PORT/UNIT
- go-eCharger (MQTT): `src/mqtt_client/config/goe.json` → MQTT-Konfiguration
  - Unterstützt 2 Formate:
    - Legacy:
      ```json
      {
        "broker": "192.168.188.97",
        "prefix": ["go-eCharger/254959/"],
        "subscribe": ["alw", "amp", "car", "cus", "dwo", "eto", "frc", "wh", "nrg", "tma", "psm", "modelStatus"],
        "setMap": {
          "amp": "go-eCharger/254959/amp/set",
          "frc": "go-eCharger/254959/frc/set",
          "psm": "go-eCharger/254959/psm/set"
        }
      }
      ```
    - Reviewed (vereinfacht, pro PR-Kommentar):
      ```json
      {
        "broker_ip": "192.168.188.97",
        "goE": [
          "go-eCharger/254959/alw",
          "go-eCharger/254959/amp",
          "go-eCharger/254959/car",
          "go-eCharger/254959/cus",
          "go-eCharger/254959/dwo",
          "go-eCharger/254959/eto",
          "go-eCharger/254959/frc",
          "go-eCharger/254959/wh",
          "go-eCharger/254959/nrg",
          "go-eCharger/254959/tma",
          "go-eCharger/254959/psm",
          "go-eCharger/254959/modelStatus"
        ],
        "setMap": {
          "amp": "go-eCharger/254959/amp/set",
          "frc": "go-eCharger/254959/frc/set",
          "psm": "go-eCharger/254959/psm/set"
        }
      }
      ```
  - Werte werden unter ihrem letzten Topic-Segment im Dict abgelegt, z. B. `state["alw"]` für `.../alw`.
- Influx Buckets: `influx_bucket/influxConfig`

5) Starten

```
python -m src.main
```

## Services
- Autostart-Skripte unter `service/` und `src/autostart_script.sh`

## Änderungen in diesem Branch
- CPU-Spin im Main-Loop verhindert (asyncio sleep)
- Format-String Bug in `task_30s` gefixt
- Influx-Feldnamen für PV3/PV4 korrigiert
- Point-Erstellung vereinfacht (kein Überschreiben des Tags)
- requirements.txt hinzugefügt
- README erweitert
- MQTT-Service überarbeitet: Neues JSON-Format (broker_ip + goE-Liste) unterstützt; Keys = letztes Topic-Segment (z. B. "alw").
