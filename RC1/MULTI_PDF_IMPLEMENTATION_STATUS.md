# Multi-PDF Implementation Status

## Completed Components

### 1. Core Data Model (✅ COMPLETE)

**File: `digitizer/calibration.py`**
- `Calibration` class with 2-point reference transformation
  - `pdf_to_real(x, y)` - Convert PDF coordinates to real-world
  - `real_to_pdf(x, y)` - Convert real-world to PDF coordinates
  - `save(filepath)` - Save calibration to .cal file
  - `load(filepath)` - Load calibration from .cal file
  - `to_dict()` / `from_dict()` - Serialization support

- `PDFDocument` class for managing PDFs
  - `filename` - Relative path to PDF file
  - `calibration` - Associated Calibration object
  - `display_name` - User-friendly name
  - `order` - Display order in UI
  - `active` - Currently active flag
  - `to_dict()` / `from_dict()` - Serialization with calibration file loading

**File: `qt_app/models.py`**
- Updated `ProjectData` class:
  - `pdfs: List[PDFDocument]` - List of all PDFs in project
  - `active_pdf_index: int` - Index of currently active PDF
  - Legacy fields preserved for backward compatibility:
    - `reference_points_pdf` / `reference_points_real`
    - `transformation_matrix`
    - `pdf_path`
  
- PDF Management Methods:
  - `add_pdf(pdf_doc)` - Add PDF to project
  - `remove_pdf(index)` - Remove PDF by index
  - `get_active_pdf()` - Get currently active PDF
  - `set_active_pdf(index)` - Switch active PDF
  - `reorder_pdf(old_index, new_index)` - Reorder PDFs in list
  
- Serialization:
  - `to_dict()` - Saves pdfs list and active_pdf_index
  - `from_dict()` - Loads PDFs with calibration files
  - Backward compatibility with old single-PDF projects

### 2. Testing (✅ COMPLETE)

**File: `test_multi_pdf.py`**
- Basic operations tests:
  - Adding/removing PDFs
  - Getting/setting active PDF
  - Reordering PDFs
  
- Serialization tests:
  - to_dict() / from_dict() roundtrip
  - Calibration preservation
  
- Backward compatibility tests:
  - Loading old projects without 'pdfs' field
  - Legacy calibration data preservation

**Test Results:**
- All existing smoke tests pass (85/85)
- All multi-PDF tests pass (13/13)

---

## Remaining Components

### 3. UI Components (🔄 PENDING)

**PDF Manager Widget** - New Qt widget for managing PDFs
- Location: `qt_app/pdf_manager.py`
- Features needed:
  - List view showing all PDFs
  - Radio buttons for selecting active PDF
  - Add/Remove/Calibrate buttons
  - Display calibration status (calibrated/uncalibrated)
  - Reorder PDFs (drag-drop or up/down buttons)
  - Show PDF display names (editable)

**Main Window Integration**
- Add PDF Manager to main window layout
- Connect signals for PDF switching
- Update menu actions:
  - "Add PDF" - Add new PDF to project
  - "Calibrate Current PDF" - Open calibration dialog for active PDF
  - "Remove PDF" - Remove selected PDF

### 4. PDF Viewer Updates (🔄 PENDING)

**File: `qt_app/pdf_viewer.py`**
- Modify to use active PDF's calibration:
  - Replace `self.project.transformation_matrix` with active PDF's calibration
  - Use `calibration.real_to_pdf()` for coordinate conversion
  - Update point marker display when switching PDFs
  
- Point recalculation on PDF switch:
  - When switching PDFs, recalculate all point PDF coordinates
  - Use new PDF's `calibration.real_to_pdf()` on each point's real coordinates
  - Update marker positions on PDF display

### 5. Calibration Dialog Updates (🔄 PENDING)

**File: `qt_app/main_window.py` - Calibration methods**
- Update `_calibrate()` method:
  - Work with active PDF instead of project-level calibration
  - Save calibration to .cal file (e.g., `track1.pdf` → `track1.cal`)
  - Update active PDF's calibration object
  
- Per-PDF calibration:
  - Each PDF has its own 2-point reference calibration
  - Calibrations saved as separate .cal files
  - Project file references .cal files, doesn't embed calibration data

### 6. Migration Support (🔄 PENDING)

**Auto-migration of legacy projects:**
- Detect old projects (no 'pdfs' field in JSON)
- Create PDFDocument from legacy `pdf_path`
- Create Calibration from legacy reference points and transformation matrix
- Save calibration to .cal file
- Add PDFDocument to project.pdfs list
- Prompt user to save project in new format

### 7. File Path Management (🔄 PENDING)

**Relative path handling:**
- Store PDF paths relative to project file location
- Store .cal paths relative to project file location
- Convert absolute paths to relative on save
- Convert relative paths to absolute on load
- Handle missing PDF/calibration files gracefully

---

## Implementation Priority

### Phase 1: Core Integration (High Priority)
1. Update pdf_viewer.py to use active PDF calibration
2. Implement point recalculation on PDF switch
3. Update calibration dialog to save per-PDF .cal files

### Phase 2: UI (Medium Priority)
4. Create PDF Manager widget
5. Integrate PDF Manager into main window
6. Add menu actions for PDF management

### Phase 3: Polish (Low Priority)
7. Implement legacy project migration
8. Add file path management and validation
9. Handle edge cases (missing files, etc.)
10. User documentation

---

## Design Decisions

### Calibration Storage
- **Decision:** Store calibrations in separate .cal files
- **Rationale:** 
  - Keeps project files clean and focused on geometry
  - Allows reusing calibrations across projects
  - Makes it easy to update calibration without changing project
  - Follows single-responsibility principle

### Active PDF Paradigm
- **Decision:** Only one PDF active at a time
- **Rationale:**
  - Simplifies UI - only one PDF viewer needed
  - Natural workflow - work on one drawing at a time
  - All points use real-world coordinates, display coordinates calculated on-demand
  - Easy to switch between PDFs without changing geometry data

### Coordinate System
- **Decision:** Points store real-world coordinates, PDF coordinates calculated on-demand
- **Rationale:**
  - Geometry is independent of any particular PDF
  - Can view same geometry on different PDFs with different scales/orientations
  - Switching PDFs just changes display, not data
  - Follows model-view separation principle

### Backward Compatibility
- **Decision:** Preserve legacy fields, auto-migrate on first save
- **Rationale:**
  - Existing projects continue to work
  - No forced migration
  - User can keep old format or upgrade
  - Smooth transition path

---

## Testing Strategy

### Unit Tests
- [✅] Calibration coordinate transformations
- [✅] PDFDocument creation and serialization
- [✅] ProjectData multi-PDF methods
- [✅] Backward compatibility loading

### Integration Tests
- [⏳] PDF switching with point recalculation
- [⏳] Calibration dialog creates .cal files
- [⏳] Project save/load with multiple PDFs
- [⏳] Legacy project migration

### UI Tests
- [⏳] PDF Manager add/remove operations
- [⏳] Active PDF selection updates viewer
- [⏳] Calibration workflow per-PDF

---

## Next Steps

1. **Immediate:** Update `pdf_viewer.py` to use active PDF calibration
2. **Next:** Modify calibration dialog to save .cal files per PDF
3. **Then:** Create PDF Manager widget UI
4. **Finally:** Test end-to-end workflow with real project

---

## Known Issues / Questions

1. **Q:** What happens if calibration file is missing?
   **A:** PDFDocument loads without calibration, user can recalibrate

2. **Q:** Can we have uncalibrated PDFs in project?
   **A:** Yes, PDFDocument.calibration can be None, points won't display on that PDF

3. **Q:** How to handle point creation with uncalibrated PDF?
   **A:** Require calibration before allowing point creation, or show error message

4. **Q:** Should we validate that all PDFs exist on project load?
   **A:** Yes, show warning for missing PDFs but allow project to load

---

## File Structure After Full Implementation

```
project_directory/
  my_project.dig          # Project file (JSON)
  track1.pdf              # PDF document 1
  track1.cal              # Calibration for track1.pdf
  track2.pdf              # PDF document 2  
  track2.cal              # Calibration for track2.pdf
  track3.pdf              # PDF document 3 (uncalibrated)
```

**my_project.dig content:**
```json
{
  "user_points": [...],
  "lines": [...],
  "curves": [...],
  "pdfs": [
    {
      "filename": "track1.pdf",
      "calibration_file": "track1.cal",
      "display_name": "Main Track",
      "order": 0,
      "active": true
    },
    {
      "filename": "track2.pdf",
      "calibration_file": "track2.cal",
      "display_name": "Siding",
      "order": 1,
      "active": false
    },
    {
      "filename": "track3.pdf",
      "calibration_file": "track3.cal",
      "display_name": "Yard",
      "order": 2,
      "active": false
    }
  ],
  "active_pdf_index": 0
}
```

**track1.cal content:**
```json
{
  "pdf_filename": "track1.pdf",
  "reference_points_pdf": [[100.5, 200.3], [500.7, 600.9]],
  "reference_points_real": [[0.0, 0.0], [100.0, 100.0]],
  "calibrated_date": "2024-01-15T10:30:00",
  "notes": "North-south orientation, 1:100 scale"
}
```
