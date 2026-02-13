from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

app = FastAPI(title="ETA API", version="0.1.0")

# CORS: allow all for simplicity; restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def now_iso():
    return datetime.utcnow().isoformat() + 'Z'

@app.get("/api/wallbox/status")
async def wallbox_status() -> Dict[str, Any]:
    return {
        "timestamp": now_iso(),
        "amp": 8,
        "frc": 0,
        "psm": 0,
        "car": 2,
        "nrg": [0]*11 + [1234],
        "modelStatus": 1,
    }

@app.get("/api/wallbox/history")
async def wallbox_history(
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = None,
    interval: str = "5m",
):
    points: List[Dict[str, Any]] = []
    end = datetime.utcnow()
    start = end - timedelta(hours=2)
    t = start
    while t <= end:
        points.append({
            "t": t.isoformat() + 'Z',
            "amp": 6 + ((t.minute % 5) - 2),
            "currentEnergy": 1000 + (t.minute * 3),
        })
        t += timedelta(minutes=5)
    return {"series": points, "interval": interval}

@app.get("/api/inverter/summary")
async def inverter_summary():
    return {
        "timestamp": now_iso(),
        "ppv": 2400,
        "house_consumption": 1200,
        "battery_soc": 56,
    }

@app.get("/api/inverter/history")
async def inverter_history(
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = None,
    interval: str = "5m",
):
    points: List[Dict[str, Any]] = []
    end = datetime.utcnow()
    start = end - timedelta(hours=6)
    t = start
    while t <= end:
        minute = t.minute
        points.append({
            "t": t.isoformat() + 'Z',
            "ppv": 1500 + (minute * 5) % 1200,
            "house": 800 + (minute * 3) % 600,
            "battery_soc": 40 + (minute % 30) * 0.2,
        })
        t += timedelta(minutes=5)
    return {"series": points, "interval": interval}

# --- ETA Hackschnitzel-Heizung (Mock) ---
@app.get("/api/heating/summary")
async def heating_summary() -> Dict[str, Any]:
    return {
        "timestamp": now_iso(),
        "boiler_temp": 72.5,      # Kesseltemperatur (°C)
        "buffer_top": 68.3,       # Puffer oben (°C)
        "buffer_bottom": 45.8,    # Puffer unten (°C)
        "return_temp": 52.1,      # Rücklauf (°C)
        "outside_temp": 3.4,      # Außentemperatur (°C)
        "feed_rate": 35,          # Hackschnitzel-Förderrate (%)
        "burner_status": "on",   # on/off
    }

@app.get("/api/heating/history")
async def heating_history(
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = None,
    interval: str = "5m",
):
    points: List[Dict[str, Any]] = []
    end = datetime.utcnow()
    start = end - timedelta(hours=12)
    t = start
    while t <= end:
        minute = t.minute
        points.append({
            "t": t.isoformat() + 'Z',
            "boiler_temp": 70 + (minute % 10) * 0.4,
            "buffer_top": 66 + (minute % 8) * 0.3,
            "buffer_bottom": 44 + (minute % 6) * 0.25,
            "return_temp": 50 + (minute % 12) * 0.2,
            "feed_rate": 30 + (minute % 5) * 3,
        })
        t += timedelta(minutes=5)
    return {"series": points, "interval": interval}
