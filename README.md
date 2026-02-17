# Inkshade PDF Reader

A modern and intuitive desktop PDF reader built with Python and PyQt5, featuring an eye-friendly dark mode, advanced text selection and searching, annotation and drawing tools, and a sleek user interface.

> **Note:** This project is currently in **alpha** development. We have reverted to a `0.x.x` versioning scheme to better reflect this status. Previous releases used `1.x.x` tags, which will be updated in the git tags soon.

## Features

- **Advanced Text Selection:** Character-level precision for selecting, deselecting, and toggling text. Double-click to select a word, triple-click to select a line.
- **Powerful Search:** Search for keywords across the entire document and navigate between results with highlighted matches.
- **Annotations & Highlights:** Highlight or underline selected text with customizable colors. Annotations are saved alongside the PDF and support full undo/redo.
- **Freehand Drawing & Shapes:** Draw freehand, or use rectangle, circle, arrow, and line tools directly on pages with adjustable stroke width and color.
- **Save Annotations to PDF:** Export your annotations and drawings permanently into the PDF file.
- **Table of Contents Navigation:** Quickly jump to any section using the built-in TOC sidebar for documents that include one.
- **Clickable Links:** Internal and external links in the PDF are interactive, with hover tooltips and confirmation dialogs for external URLs.
- **Seamless Viewing:** Smooth scrolling and efficient page navigation with lazy page loading.
- **Customizable Zoom:** Control zoom levels with a slider, input box, or dedicated buttons.
- **Dark & Light Modes:** Instantly switch between a dark and a classic light theme for comfortable reading in any environment.
- **Optimized Performance:** Built on PyMuPDF for fast and efficient rendering.
- **Modern UI:** Clean interface with a soft color palette, rounded buttons, floating toolbars, and a borderless design.

## Upcoming Features

- **Narrate (Text-to-Speech):** A narration pipeline that uses document layout detection and TTS to read PDFs aloud is currently in development and will be available in a future release.

## Getting Started

### Running from Source

1. Clone the repository:

```bash
git clone https://github.com/dafaqboomduck/Inkshade-PDF.git
cd Inkshade-PDF
```

2. Install the dependencies:

```bash
pip install PyQt5 PyMuPDF pyperclip
```

3. Launch the application:

```bash
python inkshade/main.py
```

### Building a Standalone Executable

You can create a standalone executable for your operating system using PyInstaller.

1. Install PyInstaller:

```bash
pip install pyinstaller
```

2. Build the executable:

```bash
pyinstaller --onefile --noconsole --name "Inkshade PDF" --icon "inkshade/resources/icons/inkshade.ico" inkshade/main.py
```

The executable will be created in the `dist/` directory.

> **Note:** Icons and other resources may not be visible in the built executable, since PyInstaller does not bundle data files by default. If that happens, add the `--add-data` flag to include the resources:
>
> - **Windows:** `--add-data "inkshade/resources/icons;resources/icons"`
> - **Linux / macOS:** `--add-data "inkshade/resources/icons:resources/icons"`
>
> Full example (Windows):
> ```bash
> pyinstaller --onefile --noconsole --name "Inkshade PDF" --icon "inkshade/resources/icons/inkshade.ico" --add-data "inkshade/resources/icons;resources/icons" inkshade/main.py
> ```

### Flatpak (Linux)

A Flatpak manifest is included in the `flathub/` directory for building and distributing on Linux via Flathub.

### ⚠️ Antivirus Flagging Warning

Some antivirus vendors may flag executables built with PyInstaller as malicious. This is a known false-positive issue with PyInstaller-packaged applications. The code is compiled directly from the publicly available source in this repository and is completely safe to use.

## Contributing

Feel free to contribute to the project by forking the repository and submitting pull requests. If you find any issues, please report them on the [issue tracker](https://github.com/dafaqboomduck/Inkshade-PDF/issues).

## License

This project is licensed under the BSD 3-Clause "New" or "Revised" License. For the full license text, please see the [LICENSE](LICENSE) file in this repository.

Copyright (c) 2025 Razvan Nica (dafaqboomduck)

The software is provided "as is", without warranty of any kind. You are free to use, modify, and distribute this software in accordance with the terms of the license.