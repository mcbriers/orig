# 3D Maker Digitizer - Qt Version

## Overview
This is a complete rewrite of the 3D Maker Digitizer using PyQt6 for improved performance, better UI integration, and native 3D visualization.

## Architecture

The application is organized into separate modules for clarity and maintainability:

### Core Modules (`qt_app/`)
- **`models.py`** - Data models (Point, Line, Curve, ProjectData)
- **`geometry.py`** - Coordinate transformation and geometric calculations
- **`operations.py`** - Business logic for create/duplicate/delete operations
- **`audit.py`** - Line connectivity analysis and validation tools
- **`import_export.py`** - File I/O operations (JSON, CSV, GRASS ASCII)

### UI Modules (`qt_app/`)
- **`main_window.py`** - Main application window with menus and toolbar
- **`pdf_viewer.py`** - PDF display widget with click handling (TODO)
- **`editor_widget.py`** - Table views for points/lines/curves (TODO)
- **`viewer_3d.py`** - VTK-based 3D visualization (TODO)

### Entry Point
- **`main_qt.py`** - Application entry point

## Installation

```bash
# Install dependencies
pip install -r requirements_qt.txt

# Run the application
python main_qt.py
```

## Key Improvements Over Tkinter Version

1. **Better Architecture**
   - Separation of concerns (models, business logic, UI)
   - Easier to test and maintain
   - Reusable components

2. **Native Qt Integration**
   - Proper PDF rendering with QPdfDocument
   - Better table views with sorting/filtering
   - Professional menus and dialogs

3. **VTK Integration**
   - Embedded 3D view (no separate window)
   - Reliable point picking
   - Better performance

4. **Modern UI**
   - Native look and feel
   - Better responsiveness
   - Proper undo/redo support (planned)

## Current Status

✅ **Completed:**
- Core data models
- Geometry engine
- Business logic (operations, audit)
- Import/export functionality
- Main window structure
- Menu system
- Toolbar

🚧 **To Do:**
- PDF viewer widget
- Editor table widgets
- 3D VTK viewer
- Dialog windows
- Integration and testing

## Migration from Tkinter Version

The Qt version maintains compatibility with the existing JSON project format. You can open projects created with the Tkinter version and continue working on them.

## Development

The codebase follows these principles:
- **Separation of concerns** - UI and business logic are separate
- **Qt signals/slots** - For event-driven communication
- **Type hints** - For better code clarity
- **Dataclasses** - For clean data models

## Testing

```bash
# Run tests (when implemented)
pytest
```

## License

(Same as original project)
