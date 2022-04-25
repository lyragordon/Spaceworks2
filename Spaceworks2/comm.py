from serial.tools import list_ports
from pathlib import Path
import numpy as np
import os
import re

REQUEST_COMMAND = 'r'.encode('utf-8')
REQUEST_TIMEOUT = 30  # seconds

CAL_COMMAND = 'c'.encode('utf-8')
AVG_COMMAND = 'a'.encode('utf-8')
SHUTT_COMMAND = 's'.encode('utf-8')
THERM_COMMAND = 't'.encode('utf-8')

PING_COMMAND = 'p'.encode('utf-8')
PING_RESPONSE = 'o'.encode('utf-8')
PING_TIMEOUT = 3  # seconds
PING_INTERVAL = 5  # seconds

DF_START_SEQ = '['.encode('utf-8')
DF_END_SEQ = ']'.encode('utf-8')

CMD_START_SEQ = '<'.encode('utf-8')
CMD_END_SEQ = '>'.encode('utf-8')

FLOAT_START_SEQ = '`'.encode('utf-8')
FLOAT_END_SEQ = '~'.encode('utf-8')

DATA_FORMAT = (24, 32)

DATA_DIR = (Path(__file__).parent.parent / "data").resolve()
RUN_DIR = DATA_DIR

def list_serial_ports() -> list[str]:
    """Returns a list of available serial ports"""
    ports = []
    comports = list_ports.comports()
    if comports:
        for port in comports:
            ports.append(port.device)
    return ports

def list_baudrates() -> list[str]:
    """Lists baudrates to be used for serial communication."""
    return ["9600", "19200", "28800", "38400", "57600", "76800", "115200"]

def process_data(raw: str, c: float) -> np.ndarray:
    """Converts raw string of image data to a 2d array"""
    vector = np.array([float(i) for i in raw.split(',')]) + c #Adds the array with the calibration factor.
    array = np.reshape(vector, DATA_FORMAT)
    return np.rot90(array, k=2)

def get_run() -> int:
    """Checks which run folders exist and generates the next run number"""
    runs = [int(re.search("\d+", str(path.stem)).group())
            for path in DATA_DIR.glob('run_*')]
    return max(runs)+1 if runs != [] else 1

def init_run(run: int) -> Path:
    """generates a run folder"""
    RUN_DIR = DATA_DIR / f"run_{run}"
    RUN_DIR.mkdir(parents=True)
    return RUN_DIR

def init_dSet(dSet: int,run: Path) -> Path:
    dSet_dir = run / f"dataSet{dSet}"
    dSet_dir.mkdir(parents=True)
    return dSet_dir

def remove_run_dir(run: int):
    """removes a run folder"""
    run_dir = DATA_DIR / f"run_{run}"
    os.rmdir(run_dir)

def is_command(raw: bytes) -> bool:
    return True if raw[0] == int.from_bytes(CMD_START_SEQ, 'little') and raw[-1] == int.from_bytes(CMD_END_SEQ, 'little') else False

def decode_command(raw: bytes) -> str:
    return raw[1:-1].decode('utf-8')

def is_dataframe(raw: bytes) -> bool:
    return True if raw[0] == int.from_bytes(DF_START_SEQ, 'little') and raw[-1] == int.from_bytes(DF_END_SEQ, 'little') else False

def decode_df(raw: bytes) -> str:
    return raw[1:-1].decode('utf-8')

def is_float(raw: bytes) -> bool:
    return True if raw[0] == int.from_bytes(FLOAT_START_SEQ,'little') and raw[-1] == int.from_bytes(FLOAT_END_SEQ, 'little') else False