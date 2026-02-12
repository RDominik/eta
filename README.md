# eta

## Docker Start (Web UI + API)

Schnellstart lokal mit Docker Compose:

```
docker compose -f docker-compose.webui.yml up --build -d
# Web UI:   http://localhost:8080
# API (opt): http://localhost:8081
```

Nur Web UI bauen/starten (ohne Compose):

```
# Image bauen
docker build -f webui/Dockerfile -t eta-webui .
# Starten
docker run --rm -p 8080:8080 eta-webui
```

Nur API bauen/starten (ohne Compose):

```
# Image bauen
docker build -f api/Dockerfile -t eta-api .
# Starten
docker run --rm -p 8081:8081 eta-api
# Test: http://localhost:8081/api/inverter/summary
```
