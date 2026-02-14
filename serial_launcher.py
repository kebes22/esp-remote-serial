"""
esp_rfc2217_server Launcher – cross-platform GUI (Windows / macOS / Linux).

Presents a dropdown of available serial ports, a configurable TCP port,
and launches esp_rfc2217_server as a child process.
"""

import importlib
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

REQUIRED_PACKAGES = {
    # import_name -> pip_name
    "serial": "pyserial",
    "esptool": "esptool",
}


def ensure_dependencies() -> list[str]:
    """Check for missing packages and install them. Returns list of errors."""
    missing: list[tuple[str, str]] = []
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing.append((import_name, pip_name))

    if not missing:
        return []

    pip_names = [pip for _, pip in missing]
    print(f"Installing missing dependencies: {', '.join(pip_names)} ...")

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", *pip_names],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return [f"pip install failed:\n{result.stderr}"]

    # Verify imports work after install
    errors: list[str] = []
    for import_name, pip_name in missing:
        try:
            importlib.import_module(import_name)
        except ImportError:
            errors.append(f"Failed to import '{import_name}' after installing '{pip_name}'.")
    return errors


class SerialPortPicker(tk.Tk):
    """Main application window."""

    MIN_WIDTH = 500
    HEIGHT = 380
    DEFAULT_TCP_PORT = 2217

    def __init__(self):
        super().__init__()
        self.title("ESP Remote Serial Port Service")
        self.resizable(False, False)
        self._width = self.MIN_WIDTH
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._selected_port: str | None = None
        self._process: subprocess.Popen | None = None
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

        # Row 2 – TCP port
        ttk.Label(frame, text="TCP port:").grid(
            row=2, column=0, sticky="w", pady=(12, 0)
        )
        self._tcp_port_var = tk.StringVar(value=str(self.DEFAULT_TCP_PORT))
        tcp_entry = ttk.Entry(frame, textvariable=self._tcp_port_var, width=8)
        tcp_entry.grid(row=2, column=1, sticky="e", pady=(12, 0))

        # Row 3 – launch / stop buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))

        self._launch_btn = ttk.Button(
            btn_frame, text="Start", command=self._on_launch
        )
        self._launch_btn.pack(side="left", padx=(0, 6))

        self._stop_btn = ttk.Button(
            btn_frame, text="Stop", command=self._on_stop, state="disabled"
        )
        self._stop_btn.pack(side="left")

        # Row 4 – log output
        self._log = scrolledtext.ScrolledText(
            frame, height=10, state="disabled", wrap="word",
            font=("Consolas", 9), bg="#1e1e1e", fg="#cccccc",
            insertbackground="#cccccc", selectbackground="#264f78",
        )
        self._log.grid(row=4, column=0, columnspan=2, sticky="nswe", pady=(12, 0))

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(4, weight=1)

    # ── Helpers ──────────────────────────────────────────────────────

    def _center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self._width) // 2
        y = (self.winfo_screenheight() - self.HEIGHT) // 2
        self.geometry(f"{self._width}x{self.HEIGHT}+{x}+{y}")

    def _refresh_ports(self):
        """Re-scan serial ports and populate the dropdown."""
        import serial.tools.list_ports
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

    def _log_append(self, text: str):
        """Append text to the log widget (thread-safe via after)."""
        def _append():
            self._log.configure(state="normal")
            self._log.insert("end", text)
            self._log.see("end")
            self._log.configure(state="disabled")
        self.after(0, _append)

    def _on_launch(self):
        idx = self._combo.current()
        if idx < 0 or idx >= len(self._ports):
            messagebox.showwarning("No port selected", "Please select a serial port first.")
            return

        tcp_port = self._tcp_port_var.get().strip()
        if not tcp_port.isdigit():
            messagebox.showwarning("Invalid TCP port", "TCP port must be a number.")
            return

        serial_port = self._ports[idx].device
        self._selected_port = serial_port

        cmd = [sys.executable, "-m", "esp_rfc2217_server", "-p", tcp_port, serial_port]
        self._log_append(f"> {' '.join(cmd)}\n")

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except FileNotFoundError:
            self._log_append("ERROR: esp_rfc2217_server not found. Install esptool:\n")
            self._log_append("  pip install esptool\n")
            return

        self._launch_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")

        # Read output in a background thread
        thread = threading.Thread(target=self._read_output, daemon=True)
        thread.start()

    def _read_output(self):
        """Stream process stdout/stderr into the log widget."""
        proc = self._process
        if proc is None or proc.stdout is None:
            return
        for line in proc.stdout:
            self._log_append(line)
        proc.wait()
        self._log_append(f"\n[Process exited with code {proc.returncode}]\n")
        self.after(0, self._reset_buttons)

    def _reset_buttons(self):
        self._launch_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._process = None

    def _on_stop(self):
        if self._process:
            self._process.terminate()
            self._log_append("\n[Stopping...]\n")

    def _on_close(self):
        if self._process:
            self._process.terminate()
        self.destroy()

    @property
    def selected_port(self) -> str | None:
        return self._selected_port


def main() -> int:
    errors = ensure_dependencies()
    if errors:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Dependency Error", "\n".join(errors))
        root.destroy()
        return 1

    # Import after dependencies are guaranteed present
    global serial  # noqa: PLW0603
    import serial.tools.list_ports  # noqa: E402

    app = SerialPortPicker()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
