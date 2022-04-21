import pyqtgraph.exporters
import pyqtgraph as pg
import numpy as np
from PyQt5 import QtCore
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import *
from PyQt5 import QtGui
from serial import Serial
import comm
import time
import dummy
import matplotlib
from pgcolorbar.colorlegend import ColorLegendItem
from typing import Tuple
from pathlib import Path

class PgImageWindow(QMainWindow):
    """Image dialog containing pyqtgraph heatmap"""

    def __init__(self, data: np.ndarray, run: int, frame: int, run_dir: Path, parent=None):
        super().__init__(parent)
        # variables
        self.data = data
        self.run_dir = run_dir
        self.frame = frame
        # Plot and ViewBox
        self.plotItem = pg.PlotItem()
        self.viewBox = self.plotItem.getViewBox()
        self.viewBox.setAspectLocked(True)
        # Heatmap ImageItem
        self.imageItem = pg.ImageItem()
        self.imageItem.setImage(np.transpose(self.data), autoLevels=True)
        self.imageItem.setAutoDownsample(True)
        # Default scaling of heatmap
        nRows, nCols = data.shape
        self.plotItem.setRange(xRange=[-5, nCols+5], yRange=[0, nRows])
        # Set colormap
        self.imageItem.setColorMap(pg.colormap.getFromMatplotlib('plasma'))
        self.plotItem.addItem(self.imageItem)
        # Generate crosshair at hottest pixel
        self.crosshair = pg.TargetItem(
            pos=[16, 12], movable=True, size=50, label=self.get_label_at_pos, labelOpts={'offset': (40, -40), 'color': 'k', 'fill': pg.mkBrush((255, 255, 255, 127))}, pen=pg.mkPen(color='k', width=3))
        self.crosshair.setPos(self.get_max_pos(self.data))
        self.plotItem.addItem(self.crosshair)
        # Generate colorbar
        self.colorLegendItem = ColorLegendItem(
            imageItem=self.imageItem,
            showHistogram=True,
            label='Temperature (°C)')
        self.colorLegendItem.setMinimumHeight(60)
        self.colorLegendItem.autoScaleFromImage()
        # Graphics Layout
        self.graphicsWidget = pg.GraphicsLayoutWidget()
        self.graphicsWidget.addItem(self.plotItem, 0, 0)
        self.graphicsWidget.addItem(self.colorLegendItem, 0, 1)
        # Window layout
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.graphicsWidget)
        # Window settings
        self.main_widget = QWidget()
        self.main_widget.setLayout(self.layout)
        self.setCentralWidget(self.main_widget)
        self.setWindowTitle(f"Run {run} - Frame {frame}")
        self.resize(1200, 800)
        self.center()
        self.save_img()
        self.save_csv()

    def center(self):
        """Centers the window in the active monitor"""
        frameGm = self.frameGeometry()
        screen = QApplication.desktop().screenNumber(
            QApplication.desktop().cursor().pos())
        centerPoint = QApplication.desktop().screenGeometry(screen).center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())

    def get_label_at_pos(self, x_flt, y_flt) -> str:
        """Generates a label for the crosshairs at a specific point"""
        x = int(x_flt)
        y = int(y_flt)
        return f"{x},{y}\n{self.data[y][x]} °C"

    def get_max_pos(self, data: np.ndarray) -> Tuple:
        """Returns the position of the center of the hottest pixel"""
        max_index = data.argmax()
        y = int(max_index/32)
        x = ((max_index) % 32)
        return x+0.5, y+0.5

    def save_img(self):
        """Saves the heatmap as a png to the current run directory"""
        exporter = pyqtgraph.exporters.ImageExporter(
            self.graphicsWidget.scene())
        exporter.export(
            str((self.run_dir / f"frame_{self.frame}.png").resolve()))

    def save_csv(self):
        """Saves the data array as a csv."""
        with open(self.run_dir / f"frame_{self.frame}.csv", 'w') as file:
            for y in self.data:
                file.write(",".join([str(x) for x in y]) + ';\n')


class MainWindow(QMainWindow):
    """Main window dialog."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # window settings
        self.run = comm.get_run()
        self.run_dir = comm.init_run(self.run)
        self.frame = 1
        self.setWindowTitle(f"Run {self.run}")
        self.setWindowIcon(self.style().standardIcon(
            getattr(QStyle, 'SP_ComputerIcon')))
        self.resize(500, 500)
        self.serial = None
        self.command_buffer = []
        self.data_buffer = []
        self.c = float(1) #Stores calibration factor.
        self.f = float(0) #Accepts float passed from serial.
        self.t = float(0) #Target value temperature.
        # prompt for serial config
        self.dlg_serial_setup = SerialSetup(self)
        # Request button that's only active when ping is reciprocated
        self.btn_request_frame = QPushButton("Request Frame", self)
        self.btn_request_frame.resize(self.btn_request_frame.sizeHint())
        self.btn_request_frame.clicked.connect(self.evt_btn_request)
        self.btn_request_frame.setEnabled(False)
        self.ping_timer = QTimer()
        self.ping_timer.setInterval(comm.PING_INTERVAL * 1000)
        self.ping_timer.timeout.connect(self.ping_serial)
        self.ping_timer.start()
        self.btn_cal = QPushButton("Thermistor Calibration", self)
        self.btn_cal.resize(self.btn_cal.sizeHint())
        self.btn_cal.clicked.connect(self.evt_cal)
        self.btn_cal.setEnabled(False)
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
        print("Button Cal.")
        timeout = time.time() + comm.REQUEST_TIMEOUT
        self.t, enter = QInputDialog.getDouble(self, 'Target Value', 'Enter target value if known.', 25, -273.15, 273.15, 3)
        print(enter)
        if enter:
            print("Enter.")
            self.serial_command(comm.AVG_COMMAND)
            print("CommAvg.")
            while self.f == 0:
                self.read_serial()
                if time.time() > timeout:
                    self.update_terminal("<center><b>REQUEST TIMEOUT</b></center>")
                    return
            self.c = float(self.f) - self.t
            self.f = float(0)
            print("AvgReceived/Calculated.")
        else:
            print("No Enter.")
            self.serial_command(comm.CAL_COMMAND)
            print("CommCal.")
            while self.f == 0:
                self.read_serial()
                if time.time() > timeout:
                    self.update_terminal("<center><b>REQUEST TIMEOUT</b></center>")
                    return
            self.c = float(self.f)
            self.f =  float(0)
            print("CalReceived.")
        self.update_terminal(f"<center><b>Calibration Factor: {self.c} </b></center>")

    def update_terminal(self, line: str):
        """Adds a line to the terminal display."""
        self.terminal.append(line)
        self.terminal.resize(self.terminal.sizeHint())
        self.vert_layout.update()

    def evt_btn_request(self):
        img_dialog = self.request_frame()
        img_dialog.show()

    def request_frame(self) -> PgImageWindow:
        """Requests a data frame over serial and displays it."""
        self.serial_command(comm.REQUEST_COMMAND)

        timeout = time.time() + comm.REQUEST_TIMEOUT
        while self.data_buffer == []:
            self.read_serial()
            if time.time() > timeout:
                self.update_terminal("<center><b>REQUEST TIMEOUT</b></center>")
                return

        raw_data = self.data_buffer.pop(0)
        try:
            array = comm.process_data(raw_data,self.c) #Passes image data with the calibration factor.
        except:
            self.update_terminal(
                "<center><b>DATAFRAME FORMAT ERROR</b></center>")
            return
        # Open Image Window
        image_dialog = PgImageWindow(
            array, self.run, self.frame, self.run_dir, self)
        self.update_terminal(
            f"<center><b>Frame {self.frame} received</b></center>")
        self.frame += 1
        return image_dialog

    def serial_connection_lost(self):
        """Notifies user that serial connection has been lost."""
        self.update_terminal(
            "<center><b>Serial connnection lost!</b></center>")
        self.evt_serial_connection_error()

    def init_serial(self, port: str, baudrate: str):
        """Initializes the serial connection."""
        if port == "Dummy":
            self.serial = dummy.DummySerial(
                dummy.get_mode_from_str(baudrate))
        else:
            try:
                self.serial = Serial(port, baudrate=int(baudrate))
            except:
                self.evt_serial_connection_error()
                return

        self.update_terminal(
            "<center><b>Serial connection initiated.</b></center>")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Prompt for close if serial active. Delete run directory if no images were saved"""
        if list(self.run_dir.glob('*')) == []:
            comm.remove_run_dir(self.run)
        if self.serial:
            reply = QMessageBox.question(
                self, "Exit?", "A serial connection is active.\nDo you really want to exit?", QMessageBox.Yes, QMessageBox.No)
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
        error = QMessageBox.critical(
            self, "Serial Error", "The serial connection has encountered an error.")
        self.btn_request_frame.setEnabled(False)
        self.btn_burst.setEnabled(False)
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
                    self.update_terminal(
                        "<center><b>Serial device not responding (PING TIMEOUT)</b></center>")
                    return
            # Read lines until a pong is found. if a line doesn't contain the pong, pass it to the terminal
            raw_line = self.command_buffer.pop(0)
            # If the 'pong' is in those lines, enable the button and pass the rest of the lines to the terminal
            if raw_line == comm.PING_RESPONSE.decode('utf-8'):
                self.btn_request_frame.setEnabled(True)
                self.btn_cal.setEnabled(True)
            # If the response isn't the pong, just deactivate the button
            else:
                self.btn_request_frame.setEnabled(False)
                self.btn_cal.setEnabled(False)
        else:
            self.btn_request_frame.setEnabled(False)
            self.btn_cal.setEnabled(False)

    def center(self):
        """Centers the window in the active monitor"""
        frameGm = self.frameGeometry()
        screen = QApplication.desktop().screenNumber(
            QApplication.desktop().cursor().pos())
        centerPoint = QApplication.desktop().screenGeometry(screen).center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())

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
        self.parent.close()

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
        if self.cbb_SerialPort.currentText() == "Dummy":
            self.cbb_Baudrate.clear()
            new_options = ["Choose a dummy mode...             "] + \
                dummy.get_modes()
            self.cbb_Baudrate.addItems(new_options)
        else:
            self.cbb_Baudrate.clear()
            new_options = ["Choose a baudrate...                      "] + \
                comm.list_baudrates()
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
        frameGm = self.frameGeometry()
        screen = QApplication.desktop().screenNumber(
            QApplication.desktop().cursor().pos())
        centerPoint = QApplication.desktop().screenGeometry(screen).center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())