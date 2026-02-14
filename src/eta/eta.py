import requests
from requests.auth import HTTPBasicAuth
import yaml
import xml.etree.ElementTree as ET
import re
# Konfiguration
base_url = "http://<ETA-IP-ODER-HOSTNAME>:8080/user"
username = "your-username"  # falls erforderlich
password = "your-password"  # falls erforderlich


# Pfad zur YAML-Datei
yaml_file = "user/network_user.yaml"

def load_ip_from_yaml(hostname):
    with open(yaml_file, "r", encoding="utf-8") as file:
        hosts = yaml.safe_load(file)
        for host in hosts:
            if host.get('hostname') == hostname:
                return host.get('ip')
    return None

# Hole die IP-Adresse für ETA.fritz.box
ip = load_ip_from_yaml("ETA.fritz.box")

if ip:
    base_url = f"http://{ip}:8080/user"
    print(f"Die URL lautet: {base_url}")
else:
    print("Hostname 'ETA.fritz.box' wurde nicht gefunden.")

def get_menu_tree():
    url = f"{base_url}/menu"

    try:
        response = requests.get(url, auth=HTTPBasicAuth(username, password), timeout=10)
        response.raise_for_status()
        print("Antwort (XML):", response.text[:200])  # Vorschau

        root = ET.fromstring(response.text)
        return root

    except requests.exceptions.RequestException as e:
        print("Fehler beim Abrufen:", e)
        return None
    except ET.ParseError as e:
        print("XML konnte nicht geparst werden:", e)
        print("Rohantwort:", response.text)
        return None

def strip_namespace(tag):
    return tag.split('}')[-1] if '}' in tag else tag

def xml_to_dict(elem):
    d = {}
    if elem.attrib:
        d.update(elem.attrib)

    children = list(elem)
    if children:
        d['children'] = [xml_to_dict(child) for child in children]
    else:
        if elem.text and elem.text.strip():
            d['value'] = elem.text.strip()
    return {strip_namespace(elem.tag): d}

def get_value_for_uri(uri):
    try:
        url = f"{base_url}/var{uri}"
        print(url)
        resp = requests.get(url, auth=HTTPBasicAuth(username, password), timeout=10)
        resp.raise_for_status()
        print(resp.text)
        root = ET.fromstring(resp.text)
        val_elem = root.find('.//{*}value')  # Sucht <value> mit Namespace
        if val_elem is not None:
            return val_elem.text.strip()
    except Exception as e:
        print(f"Fehler bei URI {uri}: {e}")
    return None

def enrich_with_values(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, dict):
                if "uri" in value:
                    uri = value["uri"]
                    if re.fullmatch(r"(\/\d+)+", uri):
                        val = get_value_for_uri(uri)
                        if val is not None:
                            value["value"] = val
                    else:
                        print(f"⏭️  URI übersprungen (nicht variabel): {uri}")
                enrich_with_values(value)
            elif isinstance(value, list):
                for item in value:
                    enrich_with_values(item)

def save_yaml(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

if __name__ == "__main__":
    try:
        root = get_menu_tree()
        parsed = xml_to_dict(root)
        print("✅ Menübaum geparst. Werte werden abgefragt ...")
        enrich_with_values(parsed)
        save_yaml(parsed, "menu_tree_with_values.yaml")
        print("✅ YAML gespeichert: menu_tree_with_values.yaml")
    except Exception as e:
        print("Fehler:", e)
