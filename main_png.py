import tkinter as tk
from app_png import PNGViewerApp

def main():
    root = tk.Tk()
    app = PNGViewerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
