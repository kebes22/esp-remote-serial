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

    MIN_WIDTH = 450
    HEIGHT = 160

    def __init__(self):
        super().__init__()
        self.title("Serial Port Launcher")
        self.resizable(False, False)
        self._width = self.MIN_WIDTH
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
            width=40,
        )
        self._combo.grid(row=1, column=0, sticky="we", padx=(0, 8))

        ttk.Button(frame, text="Refresh", command=self._refresh_ports).grid(
            row=1, column=1, sticky="e"
        )

        # Row 2 – launch button
        self._launch_btn = ttk.Button(
            frame, text="Launch", command=self._on_launch
        )
        self._launch_btn.grid(
            row=2, column=0, columnspan=2, sticky="e", pady=(16, 0)
        )

        frame.columnconfigure(0, weight=1)

    # ── Helpers ──────────────────────────────────────────────────────

    def _center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self._width) // 2
        y = (self.winfo_screenheight() - self.HEIGHT) // 2
        self.geometry(f"{self._width}x{self.HEIGHT}+{x}+{y}")

    def _refresh_ports(self):
        """Re-scan serial ports and populate the dropdown."""
        self._ports = sorted(
            serial.tools.list_ports.comports(), key=lambda p: p.device
        )
        labels = [
            f"{p.device} – {p.description}" if p.description and p.description != "n/a" else p.device
            for p in self._ports
        ]
        self._combo["values"] = labels

        if labels:
            self._combo.current(0)
            longest = max(len(l) for l in labels)
            self._combo.configure(width=longest + 2)
            self._width = max(self.MIN_WIDTH, longest * 8 + 120)
        else:
            self._port_var.set("No serial ports detected.")
        self._center_window()

    def _on_launch(self):
        idx = self._combo.current()
        if idx < 0 or idx >= len(self._ports):
            messagebox.showwarning("No port selected", "Please select a serial port first.")
            return
        self._selected_port = self._ports[idx].device
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
