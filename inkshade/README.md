## Project Structure

```
inkshade/
├── main.py                  # Application entry point
├── core/                    # Core business logic
│   ├── annotations/         # Annotation models, manager, undo/redo, persistence
│   ├── document/            # PDF loading, rendering, and export
│   ├── page/                # Page model, text layer, link layer
│   ├── search/              # Search engine and highlighting
│   ├── selection/           # Character-level selection manager
│   └── export/              # PDF export worker
├── controllers/             # Application controllers
│   ├── annotation_controller.py
│   ├── input_handler.py     # Keyboard and mouse input handling
│   ├── link_handler.py      # Link navigation and security
│   └── view_controller.py   # View state management
├── ui/                      # User interface
│   ├── windows/             # Main application window
│   ├── widgets/             # PDF viewer, interactive page labels, TOC widget
│   └── toolbars/            # Search bar, annotation toolbar, drawing toolbar
├── styles/                  # Theme manager and color definitions
├── utils/                   # Resource loading, warning manager, helpers
├── resources/               # Icons and other assets
└── flathub/                 # Flatpak build manifest and metadata
```