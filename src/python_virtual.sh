#!/bin/bash

# Einstellungen
VENV_DIR="venv"
PYTHON_SCRIPT="goodWe_influx.py"

# Virtuelle Umgebung erstellen, falls sie nicht existiert
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Erstelle virtuelle Umgebung..."
    python3 -m venv "$VENV_DIR"
fi

# Umgebung aktivieren
source "$VENV_DIR/bin/activate"

# Pakete installieren (falls noch nicht installiert)
echo "📥 Installiere benötigte Python-Pakete..."
pip install --upgrade pip
pip install goodwe influxdb-client

# Starte dein Python-Skript
echo "🚀 Starte das Python-Skript..."
python3 "$PYTHON_SCRIPT"
