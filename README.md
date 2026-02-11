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
- go-eCharger (MQTT): `src/goE/wallbox_control.py` → BROKER/PREFIX/SSE
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
