import sys
from PyQt5.QtWidgets import QApplication
from ui.pdf_reader import PDFReader

def main():
    """Main function to run the PDF reader application."""
    app = QApplication(sys.argv)
    window = PDFReader()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
