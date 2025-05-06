import os
import ipaddress
import subprocess
import platform
import socket
import requests
import yaml
from concurrent.futures import ThreadPoolExecutor

NETWORK = "192.168.188.0/24"
OUTPUT_DIR = "user"  # Neuer Ordner
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "network_user.yaml")

# Sicherstellen, dass der Ordner existiert
os.makedirs(OUTPUT_DIR, exist_ok=True)
# IP Geolocation (z.B. ipinfo.io)
GEOLOCATION_API = "https://ipinfo.io/{}/json"

def ping(ip):
    param = "-n" if platform.system().lower() == "windows" else "-c"
    result = subprocess.run(["ping", param, "1", "-w", "1000", str(ip)],
                            stdout=subprocess.DEVNULL)
    return ip if result.returncode == 0 else None

def get_hostname(ip):
    try:
        hostname = socket.gethostbyaddr(str(ip))[0]
    except socket.herror:
        hostname = None
    return hostname

def get_mac_address(ip):
    """ ARP-Abfrage für MAC-Adresse """
    if platform.system().lower() == "windows":
        result = subprocess.run(["arp", "-a", str(ip)], capture_output=True, text=True)
        if result.returncode == 0:
            # Beispiel: 192.168.0.101           00-14-22-01-23-45     dynamic
            for line in result.stdout.splitlines():
                if str(ip) in line:
                    return line.split()[1]
    else:
        result = subprocess.run(["arp", "-n", str(ip)], capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if str(ip) in line:
                    return line.split()[3]
    return None

def get_geolocation(ip):
    """ Geolocation über ipinfo.io API """
    try:
        response = requests.get(GEOLOCATION_API.format(ip))
        data = response.json()
        return data.get("city", "unbekannt"), data.get("country", "unbekannt")
    except requests.exceptions.RequestException:
        return "unbekannt", "unbekannt"

def scan_network(network):
    net = ipaddress.ip_network(network, strict=False)
    alive_hosts = []

    with ThreadPoolExecutor(max_workers=100) as executor:
        results = executor.map(ping, net.hosts())
        for ip in results:
            if ip:
                hostname = get_hostname(ip)
                mac_address = get_mac_address(ip)
                city, country = get_geolocation(ip)

                alive_hosts.append({
                    "ip": str(ip),
                    "hostname": hostname or "unbekannt",
                    "mac_address": mac_address or "unbekannt",
                    "city": city,
                    "country": country
                })

    return alive_hosts

def save_to_yaml(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

def print_devices(devices):
    print("\nGefundene Geräte:")
    print("-" * 60)
    for dev in devices:
        print(f"IP-Adresse: {dev['ip']:15} Hostname: {dev['hostname']} MAC-Adresse: {dev['mac_address']} City: {dev['city']} Country: {dev['country']}")
    print("-" * 60)

if __name__ == "__main__":
    print("Scanne Netzwerk...")
    devices = scan_network(NETWORK)
    save_to_yaml(devices, OUTPUT_FILE)
    print_devices(devices)
    print(f"{len(devices)} Geräte gefunden. Ergebnisse gespeichert in '{OUTPUT_FILE}'.")
