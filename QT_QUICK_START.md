# Qt Application - Quick Start Guide

## ✅ Application is Running!

The Qt-based 3D Maker Digitizer is now operational.

## Current Features

### 📄 PDF Viewer Tab
- Load PDF files via **File → Load PDF**
- Zoom controls (-, +, Reset buttons)
- Page navigation (Prev, Next, page number)
- Click handling for point creation and calibration

### 📊 2D Editor Tab  
- Three sub-tabs: **Points**, **Lines**, **Curves**
- Sortable tables (click column headers)
- **Right-click context menus**:
  - Duplicate Point (specify new Z)
  - Delete Point/Line/Curve
  - Show References (for points)

### 🎯 Toolbar Modes
- **Calibration**: Click two reference points on PDF, enter real-world coordinates
- **Coordinates**: Click PDF to create points at current Z level
- **Lines**: Click start point, then end point
- **Curves**: Click start point, center point, then end point

### 💾 File Operations
- **New Project** (Ctrl+N)
- **Open Project** (Ctrl+O) - loads existing JSON files
- **Save** (Ctrl+S) / **Save As** (Ctrl+Shift+S)
- **Export**: Points/Lines/Curves to CSV, GRASS ASCII format

### 🔧 Tools Menu
- **Validate Project**: Check for issues (isolated points, zero-length lines, etc.)
- **Line Audit**: Trace connectivity (to be implemented)

## Typical Workflow

1. **File → Load PDF** - Open your track plan
2. **Tools → Calibrate** or click **Calibration** mode button
   - Click two reference points on PDF
   - Enter their real-world coordinates
   - Transformation is calculated automatically
3. **Switch to Coordinates mode**
   - Set Z level in toolbar
   - Click on PDF to create points
4. **Switch to Lines mode**
   - Click two existing points to create a line
5. **Switch to Curves mode**
   - Click three points (start, center, end) to create a curve
6. **Use 2D Editor tab** to:
   - View all entities in tables
   - Sort by any column
   - Right-click to duplicate or delete
   - Check references
7. **File → Save Project** to save your work

## What's Working

✅ Complete UI framework  
✅ PDF rendering and click handling  
✅ Point creation with calibration  
✅ Line and curve creation  
✅ Duplicate/delete operations  
✅ Reference tracking  
✅ Project save/load  
✅ CSV and GRASS ASCII export  
✅ Validation tools  

## What's Not Yet Implemented

🚧 3D View tab - VTK viewer (placeholder shown)  
🚧 Line Audit dialog - connectivity visualization  

## Compared to Tkinter Version

**Advantages:**
- ✅ Cleaner architecture
- ✅ Better performance
- ✅ Professional UI
- ✅ Native Qt widgets
- ✅ Sortable tables
- ✅ Context menus
- ✅ Better PDF rendering

**Missing:**
- 3D visualization (VTK widget not yet implemented)
- Some advanced features from Tkinter version

## Testing

Try these actions:
1. Load the `zf.dig` project if available (File → Open Project)
2. Load a PDF if you have one
3. Create a few points in Coordinates mode
4. Create lines between them
5. Use the 2D Editor to view/sort/filter
6. Right-click to access context menus
7. Export to CSV or GRASS ASCII

The application is fully functional for 2D digitization work!
