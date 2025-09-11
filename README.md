# Inkshade PDF Reader

A modern and intuitive desktop PDF reader built with Python and PyQt5, featuring advanced text selection and a sleek user interface.

## Features
- Advanced Text Selection: Select, deselect, and toggle text with precise, word-by-word control.

- Seamless Viewing: Enjoy smooth scrolling and navigation through PDF documents.

- Real-time Zoom: Adjust the zoom level with a slider, input box, or buttons for a perfect fit.

- Dark & Light Modes: Instantly toggle between a comfortable dark theme and a classic light theme.

- Optimized Performance: Built on PyMuPDF, ensuring fast and efficient rendering of pages.

## Download the App
For immediate use without any installation, download the latest pre-built executable for Windows:

[Download the Inkshade PDF.exe](https://github.com/dafaqboomduck/Inkshade-PDF/releases/latest/download/Inkshade.PDF.exe)

## Alternative Installation
To get started, clone the repository and install the required Python libraries.

1. Clone the repository:

```bash
git clone [https://github.com/dafaqboomduck/Inkshade-PDF.git](https://github.com/dafaqboomduck/Inkshade-PDF.git)
cd Inkshade-PDF
```

2. Install the dependencies:

```bash
pip install PyQt5 PyMuPDF pyperclip
```

## Usage
You can launch the application in a few different ways:

### Launching the Application
From the command line, run the main script:

```python
python main.py
```

### Opening a PDF
Once the application is running, you can open a PDF file by:

- Clicking the Open PDF button.

- Dragging and dropping a PDF file onto the application window.

## Creating an Executable
This section is for developers who want to build the application from the source code.

First, install PyInstaller:

```python
pip install pyinstaller
```

Then, run the following command to create a standalone executable with the custom name and icon:

```python
pyinstaller --onefile --noconsole --name "Inkshade PDF" --icon "resources/icons/inkshade.ico" main.py
```

Your executable will be created in the `dist/` directory.

Project Structure
- `main.py`: The application's entry point, responsible for initializing the main window.

- `pdf_reader.py`: Contains the core logic for the PDF reader window, including UI elements and functionality.

- `page_label.py`: A custom QLabel subclass that handles rendering pages and managing all text selection logic.

- `styles.py`: Defines the visual style and themes (dark and light mode) for the application's widgets.

Feel free to contribute to the project by forking the repository and submitting pull requests. If you find any issues, please report them!