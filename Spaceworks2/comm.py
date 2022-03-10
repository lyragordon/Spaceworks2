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

DF_START_SEQ = '['.encode('utf-8')
DF_END_SEQ = ']'.encode('utf-8')

DATA_FORMAT = (24, 32)

SCRIPT_DIR = Path(__file__)
DATA_DIR = (SCRIPT_DIR.parent.parent / "data").resolve()


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


def process_data(raw: str) -> np.ndarray:
    vector = np.array([float(i) for i in raw[1:-1].split(',')])
    array = np.reshape(vector, DATA_FORMAT)
    return array


def get_run() -> int:
    runs = [int(re.search("\d+", str(path.stem)).group())
            for path in DATA_DIR.glob('run_*')]
    return max(runs)+1 if runs != [] else 1


def init_run(run: int) -> Path:
    run_dir = DATA_DIR / f"run_{run}"
    run_dir.mkdir(parents=True)
    return run_dir


def remove_run_dir(run: int):
    run_dir = DATA_DIR / f"run_{run}"
    os.rmdir(run_dir)
