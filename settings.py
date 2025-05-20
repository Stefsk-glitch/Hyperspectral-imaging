from tkinter import Toplevel, Frame, ttk, StringVar, Entry, Label, Button
from models import camera_data, app_context
from lib.spectralcam.specim import FXBase

def open_settings_window(master):
    def item_selected(event):
        selected_item = tree.focus()
        if not selected_item:
            return
        values = tree.item(selected_item, 'values')
        if len(values) == 2:
            set_value_window(values[0], values[1])

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
    tree.tag_bind("click", "<<TreeviewSelect>>", item_selected)
    scrollbar.pack(side="right", fill="y")

    all_rows = []
    cam: FXBase = camera_data["cam"]

    def load_settings():
        all_rows.clear()
        features = cam.get_features()
        for feature in sorted(features, key=lambda f: str(f.node.name).lower()):
            try:
                value = cam.get(feature)
            except Exception:
                value = "N/A"
            all_rows.append((str(feature.node.name), str(value)))
        search_var.set("")
        update_treeview(all_rows)

    def update_treeview(rows):
        for item in tree.get_children():
            tree.delete(item)
        for setting, value in rows:
            tree.insert("", "end", values=(setting, value), tags="click")

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

    def confirm_set_value(setting, value, window):
        try:
            cam.set(setting, value)
            window.destroy()
            load_settings()
        except Exception as error:
            app_context["message_box"](error)

    def set_value_window(setting, value):
        win = Toplevel(master)
        win.title("Set Value")
        Label(win, text=setting).pack()
        Label(win, text=value).pack()
        entry_var = StringVar()
        entry = Entry(win, textvariable=entry_var)
        entry.pack()
        Button(win, text="Save", command=lambda:confirm_set_value(setting, entry_var.get(), win)).pack()

    load_settings()
    