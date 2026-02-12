
from pymodbus.client.tcp import ModbusTcpClient
from pymodbus.exceptions import ModbusIOException
import struct
import json
from pathlib import Path
IP = "192.168.188.200"   # IP deines RS485 → ETH Adapters
PORT = 4196
UNIT = 247   
class modbus_client:
    client: ModbusTcpClient
    register: dict
    unit: int    # GoodWe ET Modbus Adresse

    def __init__(self, ip: str, port: int, unit: int, config_json: Path, config_json2: Path=None):       
        self.client = ModbusTcpClient(ip, port=port, timeout=2)
        self.register = self.load_registers(config_json)
        self.register2 = self.load_registers(config_json2)
        self.unit = unit

    def load_registers(self, path: str | Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
        
    def read_register(self, register: dict) -> dict:
        count = register["count"]
        signed = register.get("signed", False)
        factor = register.get("factor", 1)
        floating = register.get("floating", False)
        try:
            rr = self.client.read_holding_registers(
                register["address"],
                count=count,
                device_id=self.unit
            )
        except ModbusIOException:
            return None
        
        if rr.isError():
            raise RuntimeError(rr)

        if count == 1:
        # 16-bit
            register["value"] = self.to_signed16(rr.registers[0], signed=signed, factor=factor)
        elif count == 2:
        # 32-bit (Big Endian, GoodWe-typisch)
            register["value"] = self.to_signed32(self.to_u32(rr.registers[0], rr.registers[1], floating), factor, signed)
        elif register.get("block", False) is True:
            self.return_block_values(register, rr.registers)
        else:
            raise ValueError("Unsupported register width")

        # return value * factor

        return register

    def return_block_values(self, register: dict, raw_values: list[int]) -> dict:

        index = 0
        for name, entry in register.items():

            if not self.is_register(entry):
                continue
            signed = entry.get("signed", False)
            factor = entry.get("factor", 1)
            floating = entry.get("floating", False)
            if entry["count"] == 1:
                value = self.to_signed16(raw_values[index], signed=signed, factor=factor)
            else:
                value = self.to_signed32(self.to_u32(raw_values[index], raw_values[index + 1], floating), factor, signed)
            index = index + entry["count"]
            entry["value"] = value
        return register

    def get_register1(self) -> dict:
        return self.get_values(self.register)

    def get_register2(self) -> dict:
        return self.get_values(self.register2)    

    def get_values(self, register: dict) -> dict:
        values: dict = {}
        for name, unit in register.items():
            # print(f"self: {self.read_register(unit)}")
            # values.update(self.read_register(unit))
            value = self.read_register(unit)
            # block = self.read_register(unit)
            block = unit.get("block", False)
            if block is False:
                values[name] = value
            else:
                values.update(value)
        return values
    
    def is_register(self, entry) -> bool:
        return isinstance(entry, dict) and "address" in entry

    def to_signed16(self, val: int, factor:int, signed: bool=False) -> int:
        if signed == False:
            return val * factor
        return (val - 0x10000) * factor if val & 0x8000 else val * factor
    
    def to_signed32(self, val: int, factor:int, signed: bool=False):
        if signed == False:
            return val * factor
        return (val - 0x100000000) * factor if val & 0x80000000 else val * factor
    
    def to_u32(self, val1: int, val2: int, floating: bool=False) -> int:
        if floating == True:
            return self.u32_to_float(val1, val2)
        return (val1 << 16) | val2

    def u32_to_float(self, high: int, low: int, swapped: bool = False) -> float:
        """Convert two 16-bit registers into an IEEE-754 float (big-endian registers by default)."""
        if swapped:
            packed = struct.pack(">HH", low & 0xFFFF, high & 0xFFFF)
        else:
            packed = struct.pack(">HH", high & 0xFFFF, low & 0xFFFF)
        return struct.unpack(">f", packed)[0]
      
    @property
    def get_registers(self) -> dict:
        return self.register
    