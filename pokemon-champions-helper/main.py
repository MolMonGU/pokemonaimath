import sys
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("포켓몬 챔피언스 헬퍼")
    window = MainWindow()
    window.resize(900, 620)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
