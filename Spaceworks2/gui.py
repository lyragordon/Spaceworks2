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
matplotlib.use('Qt5Agg')


class PgImageWindow(QMainWindow):
    def __init__(self, data: np.ndarray, run: int, frame: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Run {run} - Frame {frame}")
        self.data = data
        self.plotItem = pg.PlotItem()
        self.viewBox = self.plotItem.getViewBox()
        # viewBox.disableAutoRange(pg.ViewBox.XYAxes)
        self.viewBox.setAspectLocked(True)

        self.imageItem = pg.ImageItem()
        self.imageItem.setImage(np.transpose(self.data), autoLevels=True)
        nRows, nCols = data.shape
        self.plotItem.setRange(xRange=[0, nCols], yRange=[0, nRows])

        self.imageItem.setColorMap(pg.colormap.getFromMatplotlib('plasma'))
        self.plotItem.addItem(self.imageItem)

        self.crosshair = pg.TargetItem(
            pos=[16, 12], movable=True, size=50, label=self.get_label_at_pos, labelOpts={'offset': (20, 20), 'color': 'k', 'fill': pg.mkBrush((255, 255, 255, 127))}, pen=pg.mkPen(color='k', width=3))
        self.plotItem.addItem(self.crosshair)

        self.colorLegendItem = ColorLegendItem(
            imageItem=self.imageItem,
            showHistogram=True,
            label='Temperature (°C)')
        self.colorLegendItem.setMinimumHeight(60)
        self.colorLegendItem.autoScaleFromImage()
        # TODO save frame as png and csv at data/run_N/frame_N.png & frame_N.csv
        # TODO add min/max crosshairs and readouts
        self.graphicsWidget = pg.GraphicsLayoutWidget()
        self.graphicsWidget.addItem(self.plotItem, 0, 0)
        self.graphicsWidget.addItem(self.colorLegendItem, 0, 1)
        self.main_widget = QWidget()
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.graphicsWidget)
        self.main_widget.setLayout(self.layout)
        self.setCentralWidget(self.main_widget)

        self.resize(1200, 800)
        self.center()
        self.show()

    def center(self):
        frameGm = self.frameGeometry()
        screen = QApplication.desktop().screenNumber(
            QApplication.desktop().cursor().pos())
        centerPoint = QApplication.desktop().screenGeometry(screen).center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())

    def get_label_at_pos(self, x_flt, y_flt) -> str:
        x = int(x_flt)
        y = int(y_flt)
        return f"{self.data[x][y]} °C"


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
        # prompt for serial config
        self.dlg_serial_setup = SerialSetup(self)
        # Request button that's only active when ping is reciprocated
        self.btn_request_frame = QPushButton("Request", self)
        self.btn_request_frame.resize(self.btn_request_frame.sizeHint())
        self.btn_request_frame.clicked.connect(self.evt_request_frame)
        self.btn_request_frame.setEnabled(False)
        self.ping_timer = QTimer()
        self.ping_timer.setInterval(comm.PING_INTERVAL * 1000)
        self.ping_timer.timeout.connect(self.ping_serial)
        self.ping_timer.start()
        # Reset button
        self.btn_reset_serial = QPushButton("Reset", self)
        self.btn_reset_serial.resize(self.btn_reset_serial.sizeHint())
        self.btn_reset_serial.clicked.connect(self.evt_reset_serial)
        # Terminal display
        self.terminal = QTextBrowser(self)
        self.terminal_timer = QTimer()
        self.ping_timer.setInterval(500)
        self.ping_timer.timeout.connect(self.update_serial)
        self.ping_timer.start()
        # Display widgets stacked vertically
        self.vert_layout = QVBoxLayout(self)
        self.vert_layout.addWidget(self.btn_request_frame)
        self.vert_layout.addWidget(self.btn_reset_serial)
        self.vert_layout.addWidget(self.terminal)
        self.window = QWidget(self)
        self.window.setLayout(self.vert_layout)
        self.window.show()
        # window settings
        self.setCentralWidget(self.window)
        self.center()
        self.show()

    def update_terminal(self, line: str):
        """Adds a line to the terminal display."""
        # TODO also write each line to a logfile in ../data/run_x
        self.terminal.append(line)
        self.terminal.resize(self.terminal.sizeHint())
        self.vert_layout.update()

    def evt_reset_serial(self):
        """Resets the serial port on a hardware level."""
        if self.serial and not isinstance(self.serial, dummy.DummySerial):
            self.serial.setDTR(False)
            time.sleep(0.5)  # blocking, bad, i know
            self.serial.setDTR(True)
            time.sleep(0.5)

    def evt_request_frame(self):
        """Requests a data frame over serial and displays it."""
        self.serial.write(comm.REQUEST_COMMAND)
        timeout = time.time() + comm.REQUEST_TIMEOUT
        while self.serial.inWaiting() == 0:
            time.sleep(1)
            if time.time() > timeout:
                self.update_terminal("<center><b>REQUEST TIMEOUT</b></center>")
                return
        raw_data = self.serial.readline().decode('utf-8')
        try:
            array = comm.process_data(raw_data)
        except:
            self.update_terminal(
                "<center><b>DATAFRAME FORMAT ERROR</b></center>")
            return
        # TODO validate data frame (tho i sorta solved it with the try/except)

        self.image_dialog = PgImageWindow(
            array, self.run, self.frame, self)
        self.frame += 1

    def serial_connection_lost(self):
        """Notifies user that serial connection has been lost."""
        self.update_terminal(
            "<br><center><b>Serial connnection lost!</b></center><br>")
        self.evt_serial_connection_error()

    def init_serial(self, port: str, baudrate: str):
        """Initializes the serial connection and the terminal updater thread."""
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
            "<center><b>Serial connection initiated.</b></center><br>")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        # if no files were generated, delete the run directory
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
        self.serial = None
        error = QMessageBox.critical(
            self, "Serial Error", "The serial connection has encountered an error.")
        SerialSetup(self)

    def ping_serial(self):
        """Pings serial object and enables request button if it's active"""
        # This one's a bit of a doozy so I'll comment it fully
        if self.serial and self.serial.isOpen():
            # Send 'ping'
            self.serial.write(comm.PING_COMMAND)
            # Wait for a response (this should probably be done in a QThread.... whatever im not quite sure how to do it)
            timeout = time.process_time() + comm.PING_TIMEOUT
            while self.serial.inWaiting() == 0:
                if time.process_time() > timeout:
                    self.btn_request_frame.setEnabled(False)
                    self.update_terminal(
                        "<br><center><b>Serial device not responding (PING TIMEOUT)</b></center><br>")
                    return
            # Read as many lines as are available, one of which may be the 'pong'
            raw_lines = self.serial.readlines()
            # If the 'pong' is in those lines, enable the button and pass the rest of the lines to the terminal
            if comm.PING_RESPONSE in raw_lines:
                self.btn_request_frame.setEnabled(True)
                if len(raw_lines) > 1:
                    other_lines = raw_lines.pop(
                        raw_lines.index(comm.PING_RESPONSE))
                    for line in other_lines:
                        self.update_terminal(line.decode('utf-8'))
            # If the 'pong' isnt in those lines, just pass them to the terminal and deactivate the button
            else:
                self.btn_request_frame.setEnabled(False)
                for line in raw_lines:
                    self.update_terminal(line.decode('utf-8'))
        else:
            self.btn_request_frame.setEnabled(False)

    def update_serial(self):
        if self.serial and self.serial.inWaiting() > 0:
            line = self.serial.readline().decode('utf-8')
            self.update_terminal(line)
        else:
            return

    def center(self):
        frameGm = self.frameGeometry()
        screen = QApplication.desktop().screenNumber(
            QApplication.desktop().cursor().pos())
        centerPoint = QApplication.desktop().screenGeometry(screen).center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())


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
            new_options = ["Choose a dummy mode...   "] + \
                dummy.get_modes()
            self.cbb_Baudrate.addItems(new_options)
        else:
            self.cbb_Baudrate.clear()
            new_options = ["Choose a baudrate...            "] + \
                comm.list_baudrates()
            self.cbb_Baudrate.addItems(new_options)
        if saved_selection in new_options:
            self.cbb_Baudrate.setCurrentText(saved_selection)

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        if not self.parent.serial:
            self.parent.close()
        return super().closeEvent(a0)

    def center(self):
        frameGm = self.frameGeometry()
        screen = QApplication.desktop().screenNumber(
            QApplication.desktop().cursor().pos())
        centerPoint = QApplication.desktop().screenGeometry(screen).center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())
