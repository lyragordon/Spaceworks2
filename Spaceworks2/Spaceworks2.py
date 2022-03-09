from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QFile, QTextStream
import gui
import sys
import breeze_resources


if __name__ == "__main__":
    app = QApplication(sys.argv)

    file = QFile(":/dark/stylesheet.qss")
    file.open(QFile.ReadOnly | QFile.Text)
    stream = QTextStream(file)
    app.setStyleSheet(stream.readAll())

    dlgMain = gui.MainWindow()
    sys.exit(app.exec_())
