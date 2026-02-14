"""
Serial Port Launcher – cross-platform GUI (Windows / macOS / Linux).

Presents a dropdown of available serial ports with a Refresh button
and a Launch button.  The selected port string is printed to stdout
so it can be consumed by a parent process or extended later.
"""

import sys
import tkinter as tk
from tkinter import ttk, messagebox

import serial.tools.list_ports


class SerialPortPicker(tk.Tk):
    """Main application window."""

    WIDTH = 420
    HEIGHT = 180

    def __init__(self):
        super().__init__()
        self.title("Serial Port Launcher")
        self.resizable(False, False)
        self._center_window()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._selected_port: str | None = None
        self._build_ui()
        self._refresh_ports()

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        # Row 0 – label
        ttk.Label(frame, text="Select a serial port:").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )

        # Row 1 – combo + refresh
        self._port_var = tk.StringVar()
        self._combo = ttk.Combobox(
            frame,
            textvariable=self._port_var,
            state="readonly",
            width=32,
        )
        self._combo.grid(row=1, column=0, sticky="we", padx=(0, 8))

        ttk.Button(frame, text="Refresh", command=self._refresh_ports).grid(
            row=1, column=1, sticky="e"
        )

        # Row 2 – description label
        self._desc_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self._desc_var, foreground="gray").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )

        # Row 3 – launch button
        self._launch_btn = ttk.Button(
            frame, text="Launch", command=self._on_launch
        )
        self._launch_btn.grid(
            row=3, column=0, columnspan=2, sticky="e", pady=(16, 0)
        )

        # Update description when selection changes
        self._combo.bind("<<ComboboxSelected>>", self._on_selection_changed)

        frame.columnconfigure(0, weight=1)

    # ── Helpers ──────────────────────────────────────────────────────

    def _center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.WIDTH) // 2
        y = (self.winfo_screenheight() - self.HEIGHT) // 2
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

    def _refresh_ports(self):
        """Re-scan serial ports and populate the dropdown."""
        self._ports = sorted(
            serial.tools.list_ports.comports(), key=lambda p: p.device
        )
        devices = [p.device for p in self._ports]
        self._combo["values"] = devices

        if devices:
            self._combo.current(0)
            self._on_selection_changed()
        else:
            self._port_var.set("")
            self._desc_var.set("No serial ports detected.")

    def _on_selection_changed(self, _event=None):
        idx = self._combo.current()
        if 0 <= idx < len(self._ports):
            port_info = self._ports[idx]
            self._desc_var.set(port_info.description or port_info.device)

    def _on_launch(self):
        port = self._port_var.get()
        if not port:
            messagebox.showwarning("No port selected", "Please select a serial port first.")
            return
        self._selected_port = port
        self.destroy()

    def _on_close(self):
        self._selected_port = None
        self.destroy()

    @property
    def selected_port(self) -> str | None:
        return self._selected_port


def main() -> int:
    app = SerialPortPicker()
    app.mainloop()

    if app.selected_port:
        print(app.selected_port)
        return 0

    print("No port selected.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
