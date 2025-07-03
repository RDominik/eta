#!/bin/bash

# === KONFIGURATION ===
PROJECT_DIR="$(cd "$(dirname "$0")"; pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
REQUIREMENTS="$PROJECT_DIR/pyPackageList/list.txt"
SCRIPT="$PROJECT_DIR/main.py"
WATCH=1
# === Neueste Python-Version finden ===
PYTHON=$(ls /usr/bin/python3* | grep -E 'python3\.[0-9]+$' | sort -V | tail -n 1)
echo ">> Verwende Python-Interpreter: $PYTHON"

# === Virtuelle Umgebung erstellen, falls nicht vorhanden ===
if [ ! -d "$VENV_DIR" ]; then
    echo ">> Erstelle virtuelle Umgebung unter $VENV_DIR..."
    "$PYTHON" -m venv "$VENV_DIR"
fi

# === Virtuelle Umgebung aktivieren ===
source "$VENV_DIR/bin/activate"
echo ">> Virtuelle Umgebung aktiviert."

# === Anforderungen installieren ===
if [ -f "$REQUIREMENTS" ]; then
    echo ">> Installiere Pakete aus list.txt..."
    pip install --upgrade pip
    pip install -r "$REQUIREMENTS"
    echo "$REQUIREMENTS"
    pip install goodwe
    touch "$VENV_DIR/last_requirements_check"
else
    echo ">> Keine requirements.txt gefunden Ã¼berspringe Paketinstallation."
fi

# Wenn WATCH aktiv ist, starte Ãœberwachung + Neustart
if [ "$WATCH" == "1" ]; then
    echo ">> WATCH-Modus aktiv â€“ Programm startet neu bei Ã„nderungen."

    # PrÃ¼fe, ob inotifywait verfÃ¼gbar ist
    if ! command -v inotifywait &> /dev/null; then
        echo "âŒ inotifywait fehlt. Installiere es mit: sudo apt install inotify-tools"
        exit 1
    fi

    while true; do
        echo ">> Starte Python-Skript..."
        python "$SCRIPT" &
        PID=$!
        echo $PID > "$PID_FILE"

        echo ">> Überwache $SCRIPT und $REQUIREMENTS auf Änderungen..."
        inotifywait -r -e modify,close_write,move,create,delete "$PROJECT_DIR" &
        WID=$!

        # Warte darauf, dass einer der beiden Prozesse fertig wird
        wait -n $PID $WID

        # Wenn inotify ausgelöst wurde ? kill Python
        if kill -0 $PID 2>/dev/null; then
            echo ">> Änderung erkannt – beende Python-Prozess $PID..."
            kill $PID
            wait $PID 2>/dev/null
        fi
        # === NEU: Anforderungen neu installieren, falls requirements.txt geÃ¤ndert wurde
        if [ "$REQUIREMENTS" -nt "$VENV_DIR/last_requirements_check" ]; then
            echo ">> Neue requirements.txt erkannt â€“ installiere erneut..."
            pip install -r "$REQUIREMENTS"
            touch "$VENV_DIR/last_requirements_check"
        fi
        echo ">> Starte neu..."
    done

else
    echo ">> Starte einmalig: $SCRIPT"
    python "$SCRIPT"
fi
