import tkinter as tk
from app import PDFViewerApp

if __name__ == "__main__":
    root = tk.Tk()
    app = PDFViewerApp(root)
    app.run()