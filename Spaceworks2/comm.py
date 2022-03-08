from serial import Serial
from serial.tools import list_ports

REQUEST_COMMAND = 'r'.encode('utf-8')
REQUEST_TIMEOUT = 5 #seconds

def list_serial_ports() -> list[str]:
    """Returns a list of available serial ports"""
    ports = ["Dummy"]
    comports = list_ports.comports()
    if comports:
        for port in comports:
            ports.append(port.device)
    return ports



def list_baudrates() -> list[str]:
    return ["9600","115200"]