import sys
from PyQt5.QtWidgets import QApplication
from ui.pdf_reader import PDFReader

def main():
    """
    Main function to run the PDF reader application.
    It checks for a file path passed as a command-line argument.
    """
    app = QApplication(sys.argv)
    
    file_path = None
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        
    window = PDFReader(file_path)
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
