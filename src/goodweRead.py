import asyncio
import goodwe
import sqlite3
import keyboard
import time

# Datenbank vorbereiten
conn = sqlite3.connect("inverter_data.db")
cursor = conn.cursor()

# Tabelle anlegen (nur einmal)
cursor.execute("""
CREATE TABLE IF NOT EXISTS inverter_data (
    timestamp TEXT,
    key TEXT,
    value TEXT
)
""")
conn.commit()

async def main():
    print("Verbinde mit Wechselrichter...")
    inverter = await goodwe.connect('192.168.188.120', 8899, 'ET', 0, 1, 10)
    print("Verbunden. Drücke 'x' zum Beenden.")

    try:
        while not keyboard.is_pressed('x'):
            data = await inverter.read_runtime_data()
            with open("inverter_data.txt", "a", encoding="utf-8") as f:
                f.write(str(data) + "\n")
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

            # In Datenbank schreiben
            for key, value in data.items():
                cursor.execute("INSERT INTO inverter_data (timestamp, key, value) VALUES (?, ?, ?)",
                               (timestamp, key, str(value)))
            conn.commit()

            print(f"[{timestamp}] Daten geschrieben ({len(data)} Werte)")
            await asyncio.sleep(10)  # 1 Sekunde warten

    except KeyboardInterrupt:
        pass
    finally:
        print("Beendet.")
        conn.close()

asyncio.run(main())
