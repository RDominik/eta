## @file eta.py
#  @brief ETA heating system API client.
#
#  Connects to an ETA pellet heating system via its REST/XML API,
#  retrieves the menu tree, reads variable values by URI, and
#  saves the enriched data as a YAML file.

import os
import requests
from requests.auth import HTTPBasicAuth
import yaml
import xml.etree.ElementTree as ET
import re

## @name Configuration
## @{
base_url = "http://<ETA-IP-ODER-HOSTNAME>:8080/user"
username = os.environ.get("ETA_USERNAME", "your-username")
password = os.environ.get("ETA_PASSWORD", "your-password")
yaml_file = "user/network_user.yaml"
## @}


def load_ip_from_yaml(hostname: str) -> str | None:
    """@brief Look up an IP address by hostname from the network YAML file.

    @param hostname  The hostname to search for (e.g. 'ETA.fritz.box').
    @return IP address string, or None if not found.
    """
    with open(yaml_file, "r", encoding="utf-8") as file:
        hosts = yaml.safe_load(file)
        for host in hosts:
            if host.get('hostname') == hostname:
                return host.get('ip')
    return None


# Resolve ETA IP at module load time
ip = load_ip_from_yaml("ETA.fritz.box")
if ip:
    base_url = f"http://{ip}:8080/user"
    print(f"Die URL lautet: {base_url}")
else:
    print("Hostname 'ETA.fritz.box' wurde nicht gefunden.")


def get_menu_tree() -> ET.Element | None:
    """@brief Fetch the ETA menu tree via HTTP GET.

    @return Root XML Element of the menu tree, or None on error.
    """
    url = f"{base_url}/menu"
    try:
        response = requests.get(url, auth=HTTPBasicAuth(username, password), timeout=10)
        response.raise_for_status()
        print("Antwort (XML):", response.text[:200])
        return ET.fromstring(response.text)
    except requests.exceptions.RequestException as e:
        print("Fehler beim Abrufen:", e)
        return None
    except ET.ParseError as e:
        print("XML konnte nicht geparst werden:", e)
        print("Rohantwort:", response.text)
        return None


def strip_namespace(tag: str) -> str:
    """@brief Remove XML namespace prefix from a tag name.

    @param tag  Full tag string, e.g. '{http://...}name'.
    @return Tag name without namespace.
    """
    return tag.split('}')[-1] if '}' in tag else tag


def xml_to_dict(elem: ET.Element) -> dict:
    """@brief Recursively convert an XML Element tree to a nested dict.

    Attributes are merged into the dict; child elements become a
    'children' list. Leaf text content is stored under 'value'.

    @param elem  XML Element to convert.
    @return Nested dict representation.
    """
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


def get_value_for_uri(uri: str) -> str | None:
    """@brief Fetch the current value for a specific ETA variable URI.

    @param uri  ETA variable URI path (e.g. '/120/10101/0/0/12080').
    @return Value string, or None on error.
    """
    try:
        url = f"{base_url}/var{uri}"
        print(url)
        resp = requests.get(url, auth=HTTPBasicAuth(username, password), timeout=10)
        resp.raise_for_status()
        print(resp.text)
        root = ET.fromstring(resp.text)
        val_elem = root.find('.//{*}value')
        if val_elem is not None:
            return val_elem.text.strip()
    except Exception as e:
        print(f"Fehler bei URI {uri}: {e}")
    return None


def enrich_with_values(obj: dict | list) -> None:
    """@brief Recursively enrich a parsed menu tree with live values.

    Walks the dict/list structure looking for entries with a 'uri' key.
    If the URI matches the numeric pattern (e.g. /120/10101), fetches
    the live value from the ETA API and inserts it.

    @param obj  Nested dict or list from xml_to_dict().
    """
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


def save_yaml(data: dict, filename: str) -> None:
    """@brief Save data to a YAML file.

    @param data      Data structure to serialize.
    @param filename  Output file path.
    """
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
