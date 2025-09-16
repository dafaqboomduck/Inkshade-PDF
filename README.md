# Inkshade PDF Reader

A modern and intuitive desktop PDF reader built with Python and PyQt5, featuring advanced text selection and a sleek user interface.

## Features

- Advanced Text Selection: Precisely select, deselect, and toggle text word-by-word.
- Powerful Search Feature: Search for keywords in the document and navigate between results.
- Seamless Viewing: Smooth scrolling and navigation through PDF documents.
- Customizable Zoom: Control zoom levels with a slider, input box, or dedicated buttons.
- Dark & Light Modes: Instantly switch between a dark and a classic light theme for comfortable reading in any environment.
- Optimized Performance: Built on PyMuPDF, ensuring fast and efficient rendering of pages.
- Modern UI: The improved UI is more modern, clean, and easier to read, with a softer color palette, increased spacing, rounded buttons, and a borderless design for a more integrated look.

## How to Use
You can get started with Inkshade PDF in a few different ways.

### For Windows users

[Download the InkshadePDF-Installer.exe](https://github.com/dafaqboomduck/Inkshade-PDF/releases/latest/download/InkshadePDF-Installer.exe) file and double-click to run the installation process. After installation, you can find the application by searching for "Inkshade PDF" in the Windows search tool.

### ⚠️ Antivirus Flagging Warning
Some antivirus (AV) vendors may flag this application as malicious. This is a common issue with applications packaged using tools like PyInstaller. The code is compiled directly from the publicly available source in the repository and is completely safe to use.

## For developers
You can also build the application from the source code.

1. Clone the repository:

```bash
git clone [https://github.com/dafaqboomduck/Inkshade-PDF.git](https://github.com/dafaqboomduck/Inkshade-PDF.git)
cd Inkshade-PDF
```

2. Install the dependencies:

```bash
pip install PyQt5 PyMuPDF pyperclip
```

3. Launch the application:
```bash
python main.py
```

4. Create an Executable:

First, install PyInstaller:
```bash
pip install pyinstaller
```
Then, run the following command to create a standalone executable:
```bash
pyinstaller --onefile --noconsole --name "Inkshade PDF" --icon "resources/icons/inkshade.ico" main.py
```
The executable will be created in the dist/ directory.

## Project Structure
- `main.py`: The application's entry point, responsible for initializing the main window.

- `pdf_reader.py`: Contains the core logic for the PDF reader window, including UI elements and functionality.

- `page_label.py`: A custom QLabel subclass that handles rendering pages and managing all text selection logic.

- `styles.py`: Defines the visual style and themes (dark and light mode) for the application's widgets.

Feel free to contribute to the project by forking the repository and submitting pull requests. If you find any issues, please report them!

## License
This project is licensed under the BSD 3-Clause "New" or "Revised" License. For the full license text, please see the LICENSE file in this repository.

Copyright (c) 2025 Razvan Nica (dafaqboomduck)

The software is provided “as is”, without warranty of any kind. You are free to use, modify, and distribute this software in accordance with the terms of the license.