import requests
from requests.auth import HTTPBasicAuth

# Konfiguration
base_url = "http://<ETA-IP-ODER-HOSTNAME>:8080/user"
username = "your-username"  # falls erforderlich
password = "your-password"  # falls erforderlich

def get_menu_tree():
    url = f"{base_url}/menu"

    try:
        response = requests.get(url, auth=HTTPBasicAuth(username, password), timeout=10)
        response.raise_for_status()

        menu_tree = response.json()
        return menu_tree

    except requests.exceptions.RequestException as e:
        print("Fehler beim Abrufen des Menübaums:", e)
        return None

if __name__ == "__main__":
    tree = get_menu_tree()
    if tree:
        import json
        print(json.dumps(tree, indent=2))
