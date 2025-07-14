import requests
import statistics
from collections import deque

class goE_wallbox:
    def __init__(self, ip):
        self.baseURL = f"http://{ip}/api"  # Konvention: Unterstrich = "intern"

    def get_status(self, filter="alw,acu,amp,car,pnp,eto,frc"):
        # alw = car allowed to charge
        # acu = actual current, amp = max current 
        # car = carState, null if internal error (Unknown/Error=0, Idle=1, Charging=2, WaitCar=3, Complete=4, Error=5), pnp = numberOfPhases, 
        # eto = energy_total wh = energy in Wh since car connected
        response = requests.get(f"{self.baseURL}/status?filter=={filter}")
        response.raise_for_status()
        return response.json()
         
    def set_current(self, amps: int):
        """set current in Ampere (14 A)"""
        amps = max(6, min(amps, 14))
        payload = {'amp': amps}
        response = requests.get(self.baseURL + "/set", params=payload)
        response.raise_for_status()
        return response.json()  
    
    def set_charging(self, enable: bool):
        print("""start or stop charging""")
        payload = {'frc': 0 if enable else 1}
        response = requests.get(self.baseURL + "/set", params=payload)
        response.raise_for_status()
        return response.json() 

# IP-Adresse deiner go-e Wallbox
IP = "192.168.188.86"  # <- anpassen!
goE = goE_wallbox(IP)
# Basis-URL
#BASE_URL = f"http://{IP}/api"
ppvList = deque(maxlen=10)
houseConsumptionList = deque(maxlen=10)

def current_to_power(surplusPower, phases=3, voltage=230, cos_phi=0.95, minCurrent=6, maxCurrent=14):

    if surplusPower <= 0:
        return 0

    current = surplusPower / (phases * voltage * cos_phi)
    current = int(current)  # ganzzahlig runden

    if current < minCurrent:
        return 0  # Wallbox würde bei zu wenig current nicht laden

    return min(current, maxCurrent)
    
def calc_current(inverter_data, phases, charge_current=0, carState=0):
    # Einzelne Werte auslesen
    house_consumption = inverter_data["house_consumption"]
    ppv = inverter_data["ppv"]
    houseConsumptionList.append(house_consumption) 
    ppvList.append(ppv)
    ppv_mean = statistics.mean(ppvList)
    house_mean = statistics.mean(houseConsumptionList)
    
    ppv_current = current_to_power(ppv_mean)
    house_current = current_to_power(house_mean)
    if ppv_current < 6:
        target_current = 0
    elif carState == 2:  # carState == Charging
        print("Ladevorgang läuft bereits.")
        surplus_current_charging = ppv_current - (house_current-charge_current)
        if surplus_current_charging > 6:
            target_current = surplus_current_charging
        else:
            target_current = 0
    else:
        target_current = ppv_current - house_current

    battery_soc = inverter_data.get("battery_soc")
    print(f"house_consumption: {house_consumption} ")
    print(f"power photovoltaik: {ppv} ")
    print(f"battery_soc: {battery_soc} ")

  
    return target_current

def load_control(inverter_data):
    # Beispiel: Wert lesen

    """Einmal den Ladezustand abfragen und den Ladestrom setzen"""
    status = goE.get_status()
    currentTarget = calc_current(inverter_data, status["pnp"], status["acu"], status["car"])

    print("Aktueller Ladezustand:", status)
    if currentTarget >= 6:
        print(f"Setze Ladestrom auf {currentTarget}A")
        status['amp'] = goE.set_current(currentTarget)
        if status["frc"] != 0:
            goE.set_charging(True)
    else:
        if status["frc"] != 1:
            goE.set_charging(False)

    
# Beispielnutzung
if __name__ == "__main__":
    print("Ladezustand vorher:")
    print(goE.get_status())
    goE.set_current(8)
    goE.set_charging(True)
    # print("Setze Ladestrom auf 10A...")
    # print(set_current(13))

    # print("Starte Ladevorgang...")
    # set_charging(True)

    # print("Neuer Ladezustand:")
    # print(get_status())
