from serial import Serial
from serial.tools import list_ports
from pathlib import Path
import os

REQUEST_COMMAND = 'r'.encode('utf-8')
REQUEST_TIMEOUT = 5  # seconds

PING_COMMAND = 'ping'.encode('utf-8')
PING_RESPONSE = 'pong'.encode('utf-8')
PING_TIMEOUT = 0.5  # seconds
PING_INTERVAL = 2000  # milliseconds

DF_START_SEQ = '['.encode('utf-8')
DF_END_SEQ = ']'.encode('utf-8')

PWD = Path().cwd()
DATA = (PWD.parent / "data").resolve()


def list_serial_ports() -> list[str]:
    """Returns a list of available serial ports"""
    ports = ["Dummy"]
    comports = list_ports.comports()
    if comports:
        for port in comports:
            ports.append(port.device)
    return ports


def list_baudrates() -> list[str]:
    return ["9600", "115200"]
