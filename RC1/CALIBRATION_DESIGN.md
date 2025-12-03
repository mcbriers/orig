# Multi-PDF Calibration System Design

## Overview
Support multiple PDFs in a single project, each with independent calibration (scale, rotation, offset) that maps to a common real-world coordinate system.

## Data Structure

### Calibration File Format (.cal)
Each PDF gets a sidecar `.cal` file (e.g., `floor1.pdf` → `floor1.cal`)

```json
{
  "pdf_filename": "floor1.pdf",
  "reference_points_pdf": [
    [x1_pdf, y1_pdf],
    [x2_pdf, y2_pdf]
  ],
  "reference_points_real": [
    [x1_real, y1_real],
    [x2_real, y2_real]
  ],
  "calibrated_date": "2025-12-03T10:30:00",
  "notes": "First floor plan"
}
```

### Project File Enhancement
Add PDF list to `.dig` project file:

```json
{
  "pdfs": [
    {
      "filename": "floor1.pdf",
      "calibration_file": "floor1.cal",
      "active": true,
      "display_name": "Floor 1",
      "order": 1
    },
    {
      "filename": "floor2.pdf", 
      "calibration_file": "floor2.cal",
      "active": false,
      "display_name": "Floor 2",
      "order": 2
    }
  ],
  "active_pdf_index": 0,
  "user_points": [...],
  ...
}
```

## Coordinate Transformation

### PDF → Real Coordinates (Digitizing)
When user clicks on PDF:
1. Get PDF coordinates (x_pdf, y_pdf)
2. Load active PDF's calibration file
3. Apply transformation: pdf_to_real(x_pdf, y_pdf) → (x_real, y_real)
4. Store point with real coordinates

### Real → PDF Coordinates (Display)
When displaying existing points on PDF:
1. Get point's real coordinates (x_real, y_real)
2. Load current PDF's calibration file
3. Apply inverse transformation: real_to_pdf(x_real, y_real) → (x_pdf, y_pdf)
4. Draw marker at (x_pdf, y_pdf)

### Transformation Math
Using 2-point calibration:
- Calculate scale, rotation, and offset from reference points
- Apply affine transformation for each PDF independently
- Points digitized on any PDF map to the same real-world location

## User Interface Changes

### PDF Manager Panel
New sidebar panel: "PDF Documents"
```
┌─ PDF Documents ────────────┐
│ ☑ Floor 1 (active)        │
│ ☐ Floor 2                 │
│ ☐ Floor 3                 │
│                            │
│ [Add PDF...] [Remove]     │
│ [Calibrate] [Properties]  │
│ [↑] [↓] Reorder           │
└────────────────────────────┘
```

### Workflow
1. **Add PDF**: Browse to select PDF file
2. **Calibrate**: Opens calibration dialog for that PDF
3. **Switch PDF**: Click checkbox to change active PDF
   - All existing points recalculated and redrawn for new PDF
   - Hidden if they don't map within PDF bounds
4. **Remove PDF**: Removes PDF from project (points remain in real coordinates)

### Calibration Dialog
Per-PDF calibration (same as current, but saves to `.cal` file):
- Set 2 reference points on PDF
- Enter real-world coordinates
- Save calibration to `{pdf_name}.cal`

## Implementation Plan

### Phase 1: Data Layer
1. Create `Calibration` class to handle `.cal` files
2. Add `pdf_calibrations` dict to Project: `{pdf_filename: Calibration}`
3. Update Project save/load to handle multiple PDFs
4. Add coordinate transformation methods to Calibration class

### Phase 2: Core Logic
1. Modify point creation to use active PDF's calibration
2. Add method to recalculate all point PDF coordinates when switching PDFs
3. Update marker display to check if point is within current PDF bounds
4. Handle edge cases (uncalibrated PDFs, missing files)

### Phase 3: UI Components
1. Create PDF Manager widget
2. Add PDF selector to main window
3. Update calibration dialog to work per-PDF
4. Add visual indicator for active PDF
5. Show point count per PDF

### Phase 4: Polish
1. Auto-load calibration files when opening project
2. Warn if PDF file is missing
3. Export/import calibration files
4. Batch recalibration tools
5. PDF overlay mode (show multiple PDFs with transparency)

## File Management

### Directory Structure
```
project_folder/
  ├── project.dig          # Main project file
  ├── floor1.pdf
  ├── floor1.cal           # Calibration for floor1.pdf
  ├── floor2.pdf
  ├── floor2.cal           # Calibration for floor2.pdf
  └── exports/
```

### Relative Paths
Store PDF paths relative to project file:
- Makes project portable
- Easy to move/share projects
- Fallback to absolute paths if needed

## Backwards Compatibility

### Migration Strategy
1. Existing projects with single PDF:
   - Create implicit calibration from existing `reference_points_*`
   - Save as first `.cal` file
   - Maintain existing behavior

2. Old project files:
   - Detect missing `pdfs` array
   - Auto-migrate to new format
   - Keep backup of original

## Edge Cases

### Missing PDF
- Show warning message
- Allow working with other PDFs
- Keep points in real coordinates
- Re-link when PDF found

### Missing Calibration
- Detect uncalibrated PDF
- Prompt user to calibrate
- Disable digitizing until calibrated
- Show existing points without markers

### Point Visibility
- Point digitized on PDF1 may be outside bounds of PDF2
- Hide markers for out-of-bounds points
- Show in 3D view regardless of PDF
- Add "Show all points" toggle

### Coordinate Precision
- Maintain double precision in real coordinates
- Round PDF coordinates for display only
- Avoid cumulative errors from repeated transformations

## Benefits

1. **Multi-floor buildings**: Different PDF per floor
2. **Site plans**: Mix site plan + building plans
3. **Revisions**: Load new PDF without losing work
4. **Collaboration**: Different team members work on different PDFs
5. **Detail levels**: Overview + detailed sections
6. **Time series**: Historical plans vs current state

## Future Enhancements

1. **PDF Layers**: Show/hide different PDFs as layers
2. **Snap to Grid**: Per-PDF grid settings
3. **3D Integration**: Associate Z-ranges with PDFs
4. **Auto-calibration**: OCR dimension text for automatic calibration
5. **PDF Annotations**: Draw directly on PDF view
6. **Batch Import**: Import multiple PDFs at once
