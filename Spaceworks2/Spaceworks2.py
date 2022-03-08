from PyQt5.QtWidgets import QApplication
import gui
import sys

if __name__ == "__main__":
    QApplication.setStyle('Fusion')
    app = QApplication(sys.argv)
    dlgMain = gui.MainWindow()
    sys.exit(app.exec_())