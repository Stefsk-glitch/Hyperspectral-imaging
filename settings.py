from tkinter import Toplevel, Label, W, Frame, Canvas, Scrollbar, ttk, StringVar, Entry
from models import app_context, camera_data
from lib.spectralcam.specim import FXBase

def open_settings_window(master):
    win = Toplevel(master)
    win.title("Settings")
    win.geometry("800x600")

    container = Frame(win)
    container.pack(fill="both", expand=True)

    search_var = StringVar()
    search_entry = Entry(container, textvariable=search_var)
    search_entry.pack(fill="x", padx=5, pady=5)

    tree = ttk.Treeview(container, columns=("Setting", "Value"), show="headings")
    tree.heading("Setting", text="Setting")
    tree.heading("Value", text="Value")
    tree.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    cam: FXBase = camera_data["cam"]
    features = cam.get_features()
    all_rows = []
    for feature in sorted(features, key=lambda f: str(f.node.name).lower()):
        try:
            value = cam.get(feature)
        except Exception:
            value = "N/A"
        all_rows.append((str(feature.node.name), str(value)))

    def update_treeview(rows):
        for item in tree.get_children():
            tree.delete(item)
        for setting, value in rows:
            tree.insert("", "end", values=(setting, value))

    def on_search(*args):
        query = search_var.get().lower()
        if not query:
            filtered = all_rows
        else:
            filtered = [
                (setting, value)
                for setting, value in all_rows
                if query in setting.lower() or query in value.lower()
            ]
        update_treeview(filtered)

    search_var.trace_add("write", on_search)

    update_treeview(all_rows)
