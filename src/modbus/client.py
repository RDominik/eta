## @file client.py
#  @brief Generic Modbus TCP client for reading holding registers.
#
#  Provides a reusable client that reads register definitions from JSON
#  configuration files, supports 16-bit and 32-bit values (signed/unsigned),
#  IEEE-754 floats, and contiguous block reads.

from pymodbus.client.tcp import ModbusTcpClient
from pymodbus.exceptions import ModbusIOException
import struct
import json
import time
from pathlib import Path


class modbus_client:
    """@brief Modbus TCP client for reading inverter holding registers.

    Connects to a Modbus TCP gateway (e.g. RS485-to-Ethernet adapter),
    reads registers defined in JSON config files, and returns decoded values.

    @param ip          IP address of the Modbus TCP gateway.
    @param port        TCP port number.
    @param unit        Modbus device/unit address.
    @param config_json Path to the primary register configuration JSON.
    @param config_json2 Optional path to secondary register configuration JSON.
    """

    client: ModbusTcpClient
    register: dict
    unit: int

    def __init__(self, ip: str, port: int, unit: int, config_json: Path, config_json2: Path = None):
        self.client = ModbusTcpClient(ip, port=port, timeout=2)
        try:
            self.client.connect()
        except Exception:
            pass
        self.register = self.load_registers(config_json)
        self.register2 = self.load_registers(config_json2) if config_json2 else {}
        self.unit = unit

    def load_registers(self, path: str | Path) -> dict:
        """@brief Load register definitions from a JSON file.

        @param path  File path to the JSON register configuration.
        @return dict with register definitions.
        """
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def read_register(self, register: dict) -> dict:
        """@brief Read a single register or register block from the device.

        Determines the register width (16-bit, 32-bit, or block) and decodes
        the raw Modbus response accordingly. Reconnects on I/O errors.

        @param register  Register definition dict with 'address', 'count', etc.
        @return Updated register dict with 'value' field, or None on error.
        """
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
            if rr.isError():
                raise RuntimeError(rr)
        except ModbusIOException as e:
            print("Reconnect wegen:", e)
            self.client.close()
            time.sleep(10)
            self.client.connect()
            return None

        if count == 1:
            # 16-bit register
            register["value"] = self.to_signed16(rr.registers[0], signed=signed, factor=factor)
        elif count == 2:
            # 32-bit register (Big Endian, GoodWe convention)
            register["value"] = self.to_signed32(
                self.to_u32(rr.registers[0], rr.registers[1], floating), factor, signed
            )
        elif register.get("block", False) is True:
            self.return_block_values(register, rr.registers)
        else:
            raise ValueError("Unsupported register width")

        return register

    def return_block_values(self, register: dict, raw_values: list[int]) -> dict:
        """@brief Decode a contiguous block of registers into individual values.

        Iterates over sub-register entries within a block definition,
        decoding each according to its count, signedness, and factor.

        @param register    Block register definition containing sub-register entries.
        @param raw_values  List of raw 16-bit register values from the Modbus response.
        @return Updated register dict with decoded values.
        """
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
                value = self.to_signed32(
                    self.to_u32(raw_values[index], raw_values[index + 1], floating), factor, signed
                )
            index += entry["count"]
            entry["value"] = value
        return register

    def get_register1(self) -> dict:
        """@brief Read all primary (fast-cycle) registers.
        @return dict of decoded register values.
        """
        return self.get_values(self.register)

    def get_register2(self) -> dict:
        """@brief Read all secondary (slow-cycle) registers.
        @return dict of decoded register values.
        """
        return self.get_values(self.register2)

    def get_values(self, register: dict) -> dict:
        """@brief Read and decode all registers from a config dict.

        Handles both individual registers and block registers.

        @param register  Register configuration dictionary.
        @return dict mapping register names to their decoded values.
        """
        values: dict = {}
        for name, unit in register.items():
            value = self.read_register(unit)
            block = unit.get("block", False)
            if not block:
                values[name] = value
            else:
                values.update(value)
        return values

    @staticmethod
    def is_register(entry) -> bool:
        """@brief Check whether a dict entry represents a register definition.
        @param entry  Value to check.
        @return True if entry is a dict containing an 'address' key.
        """
        return isinstance(entry, dict) and "address" in entry

    @staticmethod
    def to_signed16(val: int, factor: int = 1, signed: bool = False) -> int:
        """@brief Convert a raw 16-bit register value to a (possibly signed) integer.

        @param val     Raw unsigned 16-bit value.
        @param factor  Scaling factor to apply.
        @param signed  If True, interpret as signed two's complement.
        @return Scaled integer value.
        """
        if not signed:
            return val * factor
        return (val - 0x10000) * factor if val & 0x8000 else val * factor

    @staticmethod
    def to_signed32(val: int, factor: int = 1, signed: bool = False):
        """@brief Convert a raw 32-bit register value to a (possibly signed) integer.

        @param val     Raw unsigned 32-bit value.
        @param factor  Scaling factor to apply.
        @param signed  If True, interpret as signed two's complement.
        @return Scaled integer or float value.
        """
        if not signed:
            return val * factor
        return (val - 0x100000000) * factor if val & 0x80000000 else val * factor

    def to_u32(self, val1: int, val2: int, floating: bool = False) -> int:
        """@brief Combine two 16-bit registers into a 32-bit value.

        @param val1      High word (MSB).
        @param val2      Low word (LSB).
        @param floating  If True, interpret as IEEE-754 float instead.
        @return Combined 32-bit integer or float.
        """
        if floating:
            return self.u32_to_float(val1, val2)
        return (val1 << 16) | val2

    def u32_to_float(self, high: int, low: int, swapped: bool = False) -> float:
        """@brief Convert two 16-bit registers into an IEEE-754 float.

        @param high     High word register value.
        @param low      Low word register value.
        @param swapped  If True, swap word order before conversion.
        @return Decoded float value.
        """
        if swapped:
            packed = struct.pack(">HH", low & 0xFFFF, high & 0xFFFF)
        else:
            packed = struct.pack(">HH", high & 0xFFFF, low & 0xFFFF)
        return struct.unpack(">f", packed)[0]

    @property
    def get_registers(self) -> dict:
        """@brief Property to access primary register definitions.
        @return dict of primary register configurations.
        """
        return self.register
    