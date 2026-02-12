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
