from argparse import ArgumentError
import numpy

import comm


SAMPLE = 0
RANDOM = 1
LINEAR = 2

MODES = ["SAMPLE","RANDOM","LINEAR"]

MODE_DICT ={
    "SAMPLE":SAMPLE,
    "RANDOM":RANDOM,
    "LINEAR":LINEAR
}

NUM_VALS = 24*32
RANGE = (10,30)
SPAN = RANGE[1]-RANGE[0]


class Dummy:
    """Dummy serial port that can send SAMPLE camera data, LINEAR sweep, or RANDOM data
    """

    def __init__(self, mode:int=RANDOM):
        """The one and only constructor. deal with it

        Args:
            mode (int, optional): data mode, either SAMPLE,LINEAR,or RANDOM. Defaults to SAMPLE.
        """
        self.mode = mode
        self.ready = False

    def readline(self) -> bytes:
        if self.ready:
            if self.mode == LINEAR:
                text = str([float('{:.2f}'.format(float(SPAN*i/NUM_VALS)+RANGE[0])) for i in range(NUM_VALS)])[1:-1]
            elif self.mode == RANDOM:
                lst = []
                for i in range(NUM_VALS):
                    lst.append('{:.2f}'.format(numpy.random.randint(RANGE[0]*10,RANGE[1]*10)*0.1)) 
                text = ", ".join(lst)
            elif self.mode == SAMPLE:
                raise ArgumentError("i dont have any sample data yet lol")
            else:
                raise ArgumentError("invalid mode")

            self.ready = False
            return bytes(text,encoding='utf-8')


    def isOpen(self) ->bool:
        return True
    
    def inWaiting(self) ->bool:
        return True if self.ready else False

    def write(self,cmd:bytes):
        if cmd == comm.REQUEST_COMMAND:
           self.ready = True

def get_modes() -> list[str]:
    return MODES

def get_mode_from_str(id:str) -> int:
    return MODE_DICT[id]
