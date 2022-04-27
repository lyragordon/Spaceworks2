import numpy as np
from PyQt5 import QtCore
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import *
from PyQt5 import QtGui
from serial import Serial
import comm
import time
import plotly.express as px

class MainWindow(QMainWindow):
    """Main window dialog."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # window settings
        self.run = comm.get_run()
        self.run_dir = comm.init_run(self.run)
        self.dataSet = 1
        self.frame = 1
        self.sdS = self.run_dir / "Shutter Dataset"
        self.sdS.mkdir(parents=True)
        self.setWindowTitle(f"SW2 Optics.")
        self.setWindowIcon(self.style().standardIcon(getattr(QStyle, 'SP_ComputerIcon')))
        self.resize(500, 500)
        self.serial = None
        self.command_buffer = []
        self.data_buffer = []
        self.a = np.empty([24,32])
        self.c = float(0) #Stores calibration factor.
        self.f = float(0) #Accepts float passed from serial.
        self.t = float(0) #Target value temperature.
        self.q = float(0)
        self.sFrame = 1
        # prompt for serial config
        self.dlg_serial_setup = SerialSetup(self)
        # Request button that's only active when ping is reciprocated
        self.btn_request_frame = QPushButton("Request Frame.", self)
        self.btn_request_frame.resize(self.btn_request_frame.sizeHint())
        self.btn_request_frame.clicked.connect(self.evt_btn_request)
        self.btn_request_frame.setEnabled(False)
        self.ping_timer = QTimer()
        self.ping_timer.setInterval(comm.PING_INTERVAL * 1000)
        self.ping_timer.timeout.connect(self.ping_serial)
        self.ping_timer.start()
        self.btn_cal = QPushButton("Calibrate.", self)
        self.btn_cal.resize(self.btn_cal.sizeHint())
        self.btn_cal.clicked.connect(self.evt_cal)
        self.btn_cal.setEnabled(False)
        self.btn_shutt = QPushButton("Shutter Data.", self)
        self.btn_shutt.resize(self.btn_shutt.sizeHint())
        self.btn_shutt.clicked.connect(self.evt_shutt)
        self.btn_shutt.setEnabled(False)
        # Terminal display
        self.terminal = QTextBrowser(self)

        self.serial_checker = QTimer()
        self.serial_checker.setInterval(100)
        self.serial_checker.timeout.connect(self.read_serial)
        self.serial_checker.start()
        # Display widgets stacked vertically
        self.vert_layout = QVBoxLayout(self)
        self.vert_layout.addWidget(self.btn_request_frame)
        self.vert_layout.addWidget(self.btn_cal)
        self.vert_layout.addWidget(self.btn_shutt)

        self.vert_layout.addWidget(self.terminal)
        self.window = QWidget(self)
        self.window.setLayout(self.vert_layout)
        self.window.show()
        # window settings
        self.setCentralWidget(self.window)
        self.center()
        self.show()

    def read_serial(self) -> bool:
        """checks serial port for data and loads it into appropriate buffer OR directs to terminal"""

        if self.serial:
            try:
                available = self.serial.inWaiting()
            except:
                self.evt_serial_connection_error()
            if(available):
                # trim off trailing newline character
                raw_line = self.serial.readline()[:-1]
                print(raw_line)
                if comm.is_command(raw_line):
                    self.command_buffer.insert(0, comm.decode_command(raw_line))
                elif comm.is_dataframe(raw_line):
                    self.data_buffer.insert(0, comm.decode_df(raw_line))
                elif comm.is_float(raw_line):
                    print(raw_line)
                    self.f = raw_line[1:-1].decode('utf-8')
                else:
                    self.update_terminal(raw_line.decode('utf-8'))
                return True
            else:
                return False
        else:
            return False

    def evt_cal(self):
        timeout = time.time() + comm.REQUEST_TIMEOUT
        self.t, enter = QInputDialog.getDouble(self, 'Target Value', 'Enter target value if known.', 25, -273.15, 273.15, 3)
        if enter:
            self.serial_command(comm.AVG_COMMAND)
            while self.f == 0:
                self.read_serial()
                if time.time() > timeout:
                    self.update_terminal("<center><b>REQUEST TIMEOUT.</b></center>")
                    return
            self.c = self.t - float(self.f)
            self.f = float(0)
        self.update_terminal(f"<center><b>Calibration Factor: {self.c}.</b></center>")
    
    def evt_shutt(self):
        timeout = time.time() + comm.REQUEST_TIMEOUT
        self.serial_command(comm.THERM_COMMAND)
        while self.f == 0:
            self.read_serial()
            if time.time() > timeout:
                self.update_terminal("<center><b>REQUEST TIMEOUT.</b></center>")
                return
        self.update_terminal(f"<center><b>Thermistor Value: {self.f}</b></center>")
        timeout = time.time() + comm.REQUEST_TIMEOUT
        self.serial_command(comm.SHUTT_COMMAND)
        while self.data_buffer == []:
            self.read_serial()
            if time.time() > timeout:
                self.update_terminal("<center><b>REQUEST TIMEOUT.</b></center>")
                return
        raw_data = self.data_buffer.pop(0)
        try:
            self.a = comm.process_data(raw_data,self.c) #Passes image data with the calibration factor.
        except:
            self.update_terminal("<center><b>DATAFRAME FORMAT ERROR.</b></center>")
            return
        maxHeat = np.max(self.a)
        minHeat = np.min(self.a)
        avgHeat = np.average(self.a)
        fig = px.imshow(self.a, text_auto=False, labels=dict(color="Temperaute, Celsius"), template = 'plotly_dark', title='Shutter Frame {0:g}, Minimum: {1:0.2f} Celsius, Maximum: {2:0.2f} Celsius, Average: {3:0.2f} Celsius, Thermistor Value: {4:0.2f}'.format(self.sFrame,minHeat,maxHeat,avgHeat,float(self.f)))
        fig.write_image("{}/Frame {}.png".format(self.sdS,self.sFrame))
        np.savetxt(f"{self.sdS}/Frame{self.sFrame}.csv",self.a,delimiter=",")
        fig.show()
        self.update_terminal(f"<center><b>Shutter Frame {self.sFrame} received.</b></center>")
        self.sFrame += 1

    def update_terminal(self, line: str):
        """Adds a line to the terminal display."""
        self.terminal.append(line)
        self.terminal.resize(self.terminal.sizeHint())
        self.vert_layout.update()

    def evt_btn_request(self):
        self.q, enter = QInputDialog.getInt(self, 'Frame Quantity.', 'Enter amount of pictures desired.', 1, 0, 50, 1)
        if enter:
            dS = comm.init_dSet(self.dataSet,self.run_dir)
            for i in range(self.q):
                self.request_frame()
                maxHeat = np.max(self.a)
                minHeat = np.min(self.a)
                avgHeat = np.average(self.a)
                fig = px.imshow(self.a, text_auto=False, labels=dict(color="Temperaute, Celsius"), template = 'plotly_dark', title='Dataset {0:g} Frame {1:g}, Minimum: {2:0.2f} Celsius, Maximum: {3:0.2f} Celsius, Average: {4:0.2f} Celsius.'.format(self.dataSet,self.frame,minHeat,maxHeat,avgHeat))
                fig.write_image("{}/Frame {}.png".format(dS,self.frame))
                np.savetxt(f"{dS}/Frame{self.frame}.csv",self.a,delimiter=",")
                fig.show()
                self.frame += 1
            self.update_terminal(f"<center><b>Dataset {self.dataSet} with {self.q} frames received.</b></center>")
            self.dataSet +=1
            self.frame = 1

    def request_frame(self):
        """Requests a data frame over serial and displays it."""
        self.serial_command(comm.REQUEST_COMMAND)

        timeout = time.time() + comm.REQUEST_TIMEOUT
        while self.data_buffer == []:
            self.read_serial()
            if time.time() > timeout:
                self.update_terminal("<center><b>REQUEST TIMEOUT.</b></center>")
                return

        raw_data = self.data_buffer.pop(0)
        try:
            self.a = comm.process_data(raw_data,self.c) #Passes image data with the calibration factor.
            return
        except:
            self.update_terminal("<center><b>DATAFRAME FORMAT ERROR.</b></center>")
            return

    def serial_connection_lost(self):
        """Notifies user that serial connection has been lost."""
        self.update_terminal("<center><b>Serial connnection lost!</b></center>")
        self.evt_serial_connection_error()

    def init_serial(self, port: str, baudrate: str):
        """Initializes the serial connection."""
        try:
            self.serial = Serial(port, baudrate=int(baudrate))
        except:
            self.evt_serial_connection_error()

        self.update_terminal(
            "<center><b>Serial terminal opened.</b></center>")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Prompt for close if serial active. Delete run directory if no images were saved"""
        if list(self.run_dir.glob('*')) == []:
            comm.remove_run_dir(self.run)
        if self.serial:
            reply = QMessageBox.question(self, "Exit?", "A serial connection is active.\nDo you really want to exit?", QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                event.accept()
                return super().closeEvent(event)
            else:
                event.ignore()
        else:
            event.accept()

    def evt_serial_connection_error(self):
        """Display error if serial connection dropped. Prompts for Serial setup"""
        self.serial = None
        error = QMessageBox.critical(self, "Serial Error", "The serial connection has encountered an error.")
        self.btn_request_frame.setEnabled(False)
        self.btn_cal.setEnabled(False)
        SerialSetup(self)

    def ping_serial(self):
        """Pings serial object and enables request button if it's active"""
        # This one's a bit of a doozy so I'll comment it fully
        if self.serial and self.serial.isOpen():
            # Send 'ping'
            self.serial_command(comm.PING_COMMAND)

            # Wait for a response (this should probably be done in a QThread.... whatever im not quite sure how to do it)
            timeout = time.process_time() + comm.PING_TIMEOUT
            while self.command_buffer == []:
                self.read_serial()
                if time.process_time() > timeout:
                    self.btn_request_frame.setEnabled(False)
                    self.btn_cal.setEnabled(False)
                    self.btn_shutt.setEnabled(False)
                    self.update_terminal("<center><b>Serial device not responding (PING TIMEOUT).</b></center>")
                    return
            # Read lines until a pong is found. if a line doesn't contain the pong, pass it to the terminal
            raw_line = self.command_buffer.pop(0)
            # If the 'pong' is in those lines, enable the button and pass the rest of the lines to the terminal
            if raw_line == comm.PING_RESPONSE.decode('utf-8'):
                self.btn_request_frame.setEnabled(True)
                self.btn_cal.setEnabled(True)
                self.btn_shutt.setEnabled(True)
            # If the response isn't the pong, just deactivate the button
            else:
                self.btn_request_frame.setEnabled(False)
                self.btn_cal.setEnabled(False)
                self.btn_shutt.setEnabled(False)
        else:
            self.btn_request_frame.setEnabled(False)
            self.btn_cal.setEnabled(False)
            self.btn_shutt.setEnabled(False)

    def center(self):
        """Centers the window in the active monitor"""
        self.frameGeometry().moveCenter(QApplication.desktop().screenGeometry(QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())).center())

    def serial_command(self, cmd: bytes):
        self.serial.write(comm.CMD_START_SEQ)
        self.serial.write(cmd)
        self.serial.write(comm.CMD_END_SEQ)
        self.serial.flush()


class SerialSetup(QDialog):
    """Serial port setup dialog."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # window settings
        self.parent = parent
        self.setWindowTitle("Serial Setup")
        self.setWindowIcon(self.style().standardIcon(
            getattr(QStyle, 'SP_MessageBoxQuestion')))
        self.setWindowFlags(self.windowFlags() |
                            QtCore.Qt.WindowStaysOnTopHint)
        # disables background window while this window is open
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        # ok button
        self.btn_Ok = QPushButton("Ok", self)
        self.btn_Ok.clicked.connect(self.evt_btn_Ok)
        # cancel button
        self.btn_Cancel = QPushButton("Cancel", self)
        self.btn_Cancel.clicked.connect(self.evt_btn_Cancel)
        # refresh button
        self.btn_Refresh = QPushButton(self.style().standardIcon(
            getattr(QStyle, 'SP_BrowserReload')), "", self)
        self.btn_Refresh.clicked.connect(self.evt_btn_Refresh)
        # serial port selection dropdown
        self.cbb_SerialPort = QComboBox(self)
        self.update_cbb_SerialPort()
        self.cbb_SerialPort.activated.connect(
            self.evt_cbb_SerialPort_activated)
        # baudrate selection menu
        self.cbb_Baudrate = QComboBox(self)
        self.update_cbb_Baudrate()
        # simple horizontal layout
        self.horiz_layout = QHBoxLayout()
        self.horiz_layout.addWidget(self.btn_Refresh)
        self.horiz_layout.addWidget(self.cbb_SerialPort)
        self.horiz_layout.addWidget(self.cbb_Baudrate)
        self.horiz_layout.addWidget(self.btn_Ok)
        self.horiz_layout.addWidget(self.btn_Cancel)
        self.setLayout(self.horiz_layout)
        # window settings
        self.resize(self.sizeHint())
        self.center()
        self.setFixedSize(self.size())
        self.show()
        self.setEnabled(True)

    def evt_btn_Ok(self):
        """If none of the default entries are selected, passes serial port info to main window and closes."""
        if self.cbb_SerialPort.currentText() != "Choose a serial port..." and "Choose" not in self.cbb_Baudrate.currentText():
            self.parent.init_serial(
                self.cbb_SerialPort.currentText(), self.cbb_Baudrate.currentText())
            self.close()

    def evt_btn_Refresh(self):
        """Refresh button updates dropdowns"""
        self.update_cbb_SerialPort()
        self.update_cbb_Baudrate()

    def evt_btn_Cancel(self):
        """Closes the app when 'cancel' is selected"""
        self.closeEvent()

    def evt_cbb_SerialPort_activated(self):
        """Triggered when serialport dropdown is used."""
        self.update_cbb_Baudrate()
        self.update_cbb_SerialPort()

    def update_cbb_SerialPort(self):
        """Reloads the serialport dropdown. We want to do this on every interaction to keep the serial port list up-to-date."""
        saved_selection = self.cbb_SerialPort.currentText()
        new_options = ["Choose a serial port..."] + comm.list_serial_ports()
        self.cbb_SerialPort.clear()
        self.cbb_SerialPort.addItems(new_options)
        if saved_selection in new_options:
            self.cbb_SerialPort.setCurrentText(saved_selection)

    def update_cbb_Baudrate(self):
        """Reloads the baudrate dropdown to reflect the serialport dropdown."""
        saved_selection = self.cbb_Baudrate.currentText()
        self.cbb_Baudrate.clear()
        new_options = ["Choose a baudrate...                      "] + comm.list_baudrates()
        self.cbb_Baudrate.addItems(new_options)
        if saved_selection in new_options:
            self.cbb_Baudrate.setCurrentText(saved_selection)

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        """Closes main window if setup not completed"""
        if not self.parent.serial:
            self.parent.close()
        return super().closeEvent(a0)

    def center(self):
        """Centers the window in the active monitor"""
        self.frameGeometry().moveCenter(QApplication.desktop().screenGeometry(QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())).center())