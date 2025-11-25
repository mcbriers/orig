from tkinter import simpledialog, messagebox
import numpy as np


class CalibrationMixin:
    def handle_calibration_click(self, canvas_x, canvas_y, pdf_x, pdf_y):
        self.reference_points_pdf.append((pdf_x, pdf_y))
        self.calibration_step += 1
        real_coords = self.prompt_real_coordinates(pdf_x, pdf_y)
        if real_coords is None:
            self.reference_points_pdf.pop()
            self.calibration_step -= 1
            return
        self.reference_points_real.append(real_coords)
        self.update_status(
            f"Calibration point {self.calibration_step} added: PDF({pdf_x:.1f}, {pdf_y:.1f}) → Real({real_coords[self.A]:.1f}, {real_coords[self.B]:.1f})"
        )
        size = 5
        marker_id = self.canvas.create_oval(canvas_x - size, canvas_y - size, canvas_x + size, canvas_y + size,
                                            outline="red", fill="red", tags="calibration_point", width=2)
        self.calibration_markers[len(self.reference_points_pdf) - 1] = marker_id
        self.calib_status.config(text=f"Recorded: {len(self.reference_points_pdf)} points\nStep: {self.calibration_step}")
        if len(self.reference_points_pdf) == 2:
            self.calculate_transformation()
            self.mode_var.set("coordinates")
            self.calibration_mode = False
            self.calib_status.config(text=f"Calibration complete: {len(self.reference_points_pdf)} points\nCoordinates mode active")
            self.update_status("Calibration complete. Ready to collect points.")

    def prompt_real_coordinates(self, pdf_x, pdf_y):
        prompt = f"Enter real-world coordinates for point PDF({pdf_x:.1f}, {pdf_y:.1f})\nFormat: x,y (e.g. 10.5,20.3)"
        while True:
            result = simpledialog.askstring("Real-world Coordinates", prompt)
            if result is None:
                return None
            try:
                x, y = map(float, result.split(','))
                return (x, y)
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter coordinates in format: x,y")
                # loop again

    def clear_calibration(self):
        self.reference_points_pdf.clear()
        self.reference_points_real.clear()
        self.transformation_matrix = None
        self.calibration_markers.clear()
        self.calibration_mode = False
        self.calibration_step = 0
        self.calib_status.config(text="Ready")
        if self.pdf_doc:
            self.display_page()
        self.update_status("Calibration cleared")