from serial.tools import list_ports
from pathlib import Path
import numpy as np
import os
import re


REQUEST_COMMAND = 'r'.encode('utf-8')
REQUEST_TIMEOUT = 5  # seconds

PING_COMMAND = 'ping'.encode('utf-8')
PING_RESPONSE = 'pong'.encode('utf-8')
PING_TIMEOUT = 0.5  # seconds
PING_INTERVAL = 2  # seconds

DF_START_SEQ = '/['.encode('utf-8')
DF_END_SEQ = ']/'.encode('utf-8')


DATA_FORMAT = (24, 32)

SCRIPT_DIR = Path(__file__)
DATA_DIR = (SCRIPT_DIR.parent.parent / "data").resolve()


def list_serial_ports() -> list[str]:
    """Returns a list of available serial ports"""
    ports = ["Dummy2"]
    comports = list_ports.comports()
    if comports:
        for port in comports:
            ports.append(port.device)
    return ports


def list_baudrates() -> list[str]:
    """Lists baudrates to be used for serial communication."""
    return ["9600", "19200", "28800", "38400", "57600", "76800", "115200"]


def process_data(raw: str) -> np.ndarray:
    """Converts raw string of image data to a 2d array"""
    vector = np.array([float(i) for i in raw[len(DF_START_SEQ.decode(
        'utf-8')):-1*len(DF_END_SEQ.decode('utf-8'))].split(',')])
    array = np.reshape(vector, DATA_FORMAT)
    return np.rot90(array,k=2)


def get_run() -> int:
    """Checks which run folders exist and generates the next run number"""
    runs = [int(re.search("\d+", str(path.stem)).group())
            for path in DATA_DIR.glob('run_*')]
    return max(runs)+1 if runs != [] else 1


def init_run(run: int) -> Path:
    """generates a run folder"""
    run_dir = DATA_DIR / f"run_{run}"
    run_dir.mkdir(parents=True)
    return run_dir


def remove_run_dir(run: int):
    """removes a run folder"""
    run_dir = DATA_DIR / f"run_{run}"
    os.rmdir(run_dir)
