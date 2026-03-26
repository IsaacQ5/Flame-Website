import importlib
import tkinter as tk
from tkinter import messagebox


WORKFLOW_OPTIONS = {
    "single video": {
        "module": "SingleVideo",
        "entry_point": "main",
    },
    "folder of videos": {
        "module": "AutoVideoScript",
        "entry_point": "main",
    },
}


def run_workflow(selection):
    """Imports and runs the selected workflow inside the same process."""
    option = WORKFLOW_OPTIONS[selection]
    try:
        module = importlib.import_module(option["module"])
        entry_point = getattr(module, option["entry_point"])
        entry_point()
    except SystemExit:
        raise
    except Exception as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Launch Failed",
            f"Could not start {selection}:\n{exc}",
            parent=root,
        )
        root.destroy()


class LauncherUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Flame Measurement Launcher")
        self.geometry("260x120")
        self.resizable(False, False)
        self.selection = None

        self._build_ui()
        self._center_window()
        self.bind("<Escape>", lambda _event: self.destroy())

    def _build_ui(self):
        '''Creates the buttons for each measurement workflow option.'''
        container = tk.Frame(self, padx=16, pady=16)
        container.pack(fill="both", expand=True)
        for label in WORKFLOW_OPTIONS:
            tk.Button(
                container,
                text=label,
                width=18,
                command=lambda selected=label: self.select_workflow(selected),
            ).pack(pady=6)

    def _center_window(self):
        '''Centers the launcher window on the screen.'''
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def select_workflow(self, selection):
        """Stores the selected workflow and closes the launcher window."""
        self.selection = selection
        self.destroy()


def main():
    app = LauncherUI()
    app.mainloop()
    if app.selection:
        run_workflow(app.selection)


if __name__ == "__main__":
    main()
