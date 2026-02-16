## @file ip_scan.py
#  @brief Local network scanner with hostname, MAC, and geolocation lookup.
#
#  Scans a /24 subnet via ICMP ping, resolves hostnames and MAC addresses,
#  optionally queries geolocation via ipinfo.io, and saves results to YAML.

import os
import ipaddress
import subprocess
import platform
import socket
import requests
import yaml
from concurrent.futures import ThreadPoolExecutor

## @name Configuration
## @{
NETWORK = "192.168.188.0/24"       ## Subnet to scan
OUTPUT_DIR = "user"                 ## Output directory for results
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "network_user.yaml")
GEOLOCATION_API = "https://ipinfo.io/{}/json"  ## Geolocation REST endpoint
## @}

os.makedirs(OUTPUT_DIR, exist_ok=True)


def ping(ip: ipaddress.IPv4Address) -> ipaddress.IPv4Address | None:
    """@brief Ping a single IP address with a 1-second timeout.

    @param ip  IPv4Address to ping.
    @return The IP if reachable, None otherwise.
    """
    param = "-n" if platform.system().lower() == "windows" else "-c"
    result = subprocess.run(
        ["ping", param, "1", "-w", "1000", str(ip)],
        stdout=subprocess.DEVNULL
    )
    return ip if result.returncode == 0 else None


def get_hostname(ip: ipaddress.IPv4Address) -> str | None:
    """@brief Reverse-DNS lookup for a given IP.

    @param ip  IPv4Address to resolve.
    @return Hostname string, or None if resolution fails.
    """
    try:
        return socket.gethostbyaddr(str(ip))[0]
    except socket.herror:
        return None


def get_mac_address(ip: ipaddress.IPv4Address) -> str | None:
    """@brief Retrieve MAC address via ARP table lookup.

    @param ip  IPv4Address to look up.
    @return MAC address string, or None if not found.
    """
    if platform.system().lower() == "windows":
        result = subprocess.run(["arp", "-a", str(ip)], capture_output=True, text=True)
        if result.returncode == 0:
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


def get_geolocation(ip: ipaddress.IPv4Address) -> tuple[str, str]:
    """@brief Query ipinfo.io for city and country of an IP address.

    @param ip  IPv4Address to look up.
    @return Tuple of (city, country) strings; 'unbekannt' on failure.
    """
    try:
        response = requests.get(GEOLOCATION_API.format(ip), timeout=5)
        data = response.json()
        return data.get("city", "unbekannt"), data.get("country", "unbekannt")
    except requests.exceptions.RequestException:
        return "unbekannt", "unbekannt"


def scan_network(network: str) -> list[dict]:
    """@brief Scan an entire subnet and collect device information.

    Uses a thread pool (100 workers) for parallel ping sweeps, then
    resolves hostname, MAC, and geolocation for each reachable host.

    @param network  Subnet in CIDR notation (e.g. '192.168.188.0/24').
    @return List of dicts with ip, hostname, mac_address, city, country.
    """
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


def save_to_yaml(data: list[dict], filename: str) -> None:
    """@brief Save device list to a YAML file.

    @param data      List of device dicts to serialize.
    @param filename  Output file path.
    """
    with open(filename, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)


def print_devices(devices: list[dict]) -> None:
    """@brief Pretty-print discovered devices to stdout.
    @param devices  List of device dicts.
    """
    print("\nGefundene Geräte:")
    print("-" * 60)
    for dev in devices:
        print(
            f"IP-Adresse: {dev['ip']:15} Hostname: {dev['hostname']} "
            f"MAC-Adresse: {dev['mac_address']} City: {dev['city']} Country: {dev['country']}"
        )
    print("-" * 60)


if __name__ == "__main__":
    print("Scanne Netzwerk...")
    devices = scan_network(NETWORK)
    save_to_yaml(devices, OUTPUT_FILE)
    print_devices(devices)
    print(f"{len(devices)} Geräte gefunden. Ergebnisse gespeichert in '{OUTPUT_FILE}'.")
