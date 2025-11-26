"# 3DMaker Digitizer

Interactive PDF digitizer for track definition with 2D/3D visualization and structured data export.

## Features

- **PDF Viewer**: Calibrate and digitize points, lines, and curves from PDF drawings
- **Multi-Z Support**: Handle multiple elevation levels with conflict resolution
- **3D Visualization**: Real-time matplotlib 3D view with interactive controls
- **Editor**: Inline editing, sorting, and multi-select for points/lines/curves
- **Export**: CSV and SQL output with deterministic IDs

## Requirements

- Python 3.11+
- tkinter
- PyMuPDF (fitz)
- Pillow
- NumPy
- matplotlib

## Installation

```bash
pip install pymupdf pillow numpy matplotlib
```

## Usage

```bash
python main.py
```

## Workflow

1. **Open PDF**: Load a drawing file
2. **Calibrate**: Map PDF coordinates to real-world coordinates
3. **Digitize**: Add points, lines, and curves in Coordinates/Lines/Curves modes
4. **Edit**: Use the Editor tab for inline editing and reference management
5. **Export**: Generate CSV/SQL files for downstream systems

## Project Structure

- `main.py` - Entry point
- `app.py` - Main application and UI
- `points_lines.py` - Point/line interaction handlers
- `curves.py` - Curve creation logic
- `digitizer/exporter.py` - CSV/SQL export" 
