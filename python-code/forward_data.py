import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox


# Store the last output directory next to the source files during
# development and next to the .exe when running as a frozen portable app.
if getattr(sys, "frozen", False):
    APP_ROOT = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_ROOT = os.path.dirname(os.path.abspath(__file__))

SETTINGS_PATH = os.path.join(APP_ROOT, "ui_settings.json")
SETTINGS_KEY = "last_output_dir"


def _load_last_output_dir():
    # Read the last output directory from settings if available.
    if not os.path.exists(SETTINGS_PATH):
        return None
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(SETTINGS_KEY)
    except Exception:
        return None


def _save_last_output_dir(path):
    # Persist the chosen directory for the next save dialog.
    try:
        data = {}
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        data[SETTINGS_KEY] = path
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        # If saving fails, proceed without blocking the user.
        pass


def select_output_path(
    title="Choose where to save the data",
    default_name="MeasurementData.xlsx",
):
    root = tk.Tk()
    root.withdraw()
    initial_dir = _load_last_output_dir()
    path = filedialog.asksaveasfilename(
        title=title,
        defaultextension=".xlsx",
        initialfile=default_name,
        initialdir=initial_dir,
        filetypes=[
            ("Excel Workbook", "*.xlsx"),
            ("All Files", "*.*"),
        ],
    )
    root.destroy()
    if path:
        _save_last_output_dir(os.path.dirname(path))
        return path
    return None


def main():
    path = select_output_path()
    if path:
        messagebox.showinfo("Selected Path", f"Data will be saved to:\n{path}")
        print(path)
    else:
        messagebox.showwarning("No Selection", "No location selected.")


if __name__ == "__main__":
    main()
