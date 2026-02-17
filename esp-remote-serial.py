"""
esp_rfc2217_server Service – cross-platform GUI (Windows / macOS / Linux).

Presents a dropdown of available serial ports, a configurable TCP port,
and launches esp_rfc2217_server as a child process.
"""

import argparse
import importlib
import os
import platform
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

REQUIRED_PACKAGES = {
    # import_name -> pip_name
    "serial": "pyserial",
    "esptool": "esptool",
    "psutil": "psutil",
}


def get_lock_file_path(tcp_port: int) -> str:
    """Get the lock file path for a specific TCP port."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, f".esp-serial-tcp{tcp_port}.lock")


def is_process_running(pid: int) -> bool:
    """Check if a process with given PID is running."""
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        # Fallback if psutil not available yet
        return False


def check_existing_instance(tcp_port: int) -> bool:
    """Check if an instance is already running for this TCP port. Returns True if found."""
    lock_file = get_lock_file_path(tcp_port)
    
    if not os.path.exists(lock_file):
        return False
    
    try:
        with open(lock_file, 'r') as f:
            pid_str = f.read().strip()
            if not pid_str:
                return False
            
            pid = int(pid_str)
            if is_process_running(pid):
                print(f"ESP32 Remote Serial GUI already running for TCP port {tcp_port} (PID: {pid})")
                return True
            else:
                # Stale lock file - remove it
                os.remove(lock_file)
                return False
    except (ValueError, OSError):
        # Invalid or inaccessible lock file - remove it
        try:
            os.remove(lock_file)
        except OSError:
            pass
        return False


def write_lock_file(tcp_port: int):
    """Write the current process PID to the lock file for a specific TCP port."""
    lock_file = get_lock_file_path(tcp_port)
    try:
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
    except OSError:
        pass  # Non-critical if we can't write the lock


def cleanup_lock_file(tcp_port: int | None):
    """Remove the lock file for a specific TCP port."""
    if tcp_port is None:
        return
    lock_file = get_lock_file_path(tcp_port)
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except OSError:
        pass


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

    WIDTH = 700
    HEIGHT = 380
    DEFAULT_TCP_PORT = 2217

    def __init__(self, initial_serial_port: str | None = None, initial_tcp_port: int | None = None):
        super().__init__()
        self.title("ESP32 Remote Serial Port Service")
        self.minsize(self.WIDTH, self.HEIGHT)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._selected_port: str | None = None
        self._process: subprocess.Popen | None = None
        self._initial_serial_port = initial_serial_port
        self._initial_tcp_port = initial_tcp_port
        self._locked_tcp_port: int | None = initial_tcp_port
        self._build_ui()
        self._center_window()
        self._refresh_ports()
        
        # Write lock file if we have a specific TCP port to protect
        if self._locked_tcp_port:
            write_lock_file(self._locked_tcp_port)

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

        # Row 2 – TCP port (label + entry grouped to match Refresh button)
        tcp_frame = ttk.Frame(frame)
        tcp_frame.grid(row=2, column=1, sticky="e", pady=(12, 0))
        
        # Show "(Locked)" in label if TCP port was specified via command-line
        tcp_label_text = "TCP Port (Locked):" if self._initial_tcp_port else "TCP Port:"
        ttk.Label(tcp_frame, text=tcp_label_text).pack(side="left", padx=(0, 4))
        
        tcp_value = str(self._initial_tcp_port) if self._initial_tcp_port else str(self.DEFAULT_TCP_PORT)
        self._tcp_port_var = tk.StringVar(value=tcp_value)
        
        # Make entry read-only if TCP port is locked
        tcp_state = "readonly" if self._initial_tcp_port else "normal"
        ttk.Entry(tcp_frame, textvariable=self._tcp_port_var, width=8, state=tcp_state).pack(side="left")

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
            frame, height=10, width=80, state="disabled", wrap="word",
            font=("Consolas", 9), bg="#1e1e1e", fg="#cccccc",
            insertbackground="#cccccc", selectbackground="#264f78",
        )
        self._log.grid(row=4, column=0, columnspan=2, sticky="nswe", pady=(12, 0))

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(4, weight=1)

    # ── Helpers ──────────────────────────────────────────────────────

    def _center_window(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.WIDTH) // 2
        y = (self.winfo_screenheight() - self.HEIGHT) // 2
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

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

        # Try to pre-select the initial port if specified
        selected = False
        if self._initial_serial_port and labels:
            for idx, port in enumerate(self._ports):
                if port.device == self._initial_serial_port:
                    self._combo.current(idx)
                    selected = True
                    break
        
        if not selected:
            if labels:
                self._combo.current(0)
            else:
                self._port_var.set("No serial ports detected.")

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
        cleanup_lock_file(self._locked_tcp_port)
        self.destroy()

    @property
    def selected_port(self) -> str | None:
        return self._selected_port


def launch_detached(serial_port: str | None = None, tcp_port: int | None = None) -> int:
    """Re-launch this script as a detached background process."""
    system = platform.system()
    script_path = os.path.abspath(__file__)
    
    # Build command with optional port arguments
    cmd = [script_path]
    if serial_port:
        cmd.extend(["--serial-port", serial_port])
    if tcp_port:
        cmd.extend(["--tcp-port", str(tcp_port)])
    
    # Add environment variable to mark the detached process
    env = os.environ.copy()
    env["ESP_SERIAL_BRIDGE_DETACHED"] = "1"
    
    if system == "Windows":
        # Use pythonw to avoid console window
        pythonw = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = "pythonw"  # Fallback to PATH lookup
        
        # Launch detached process without console
        subprocess.Popen(
            [pythonw] + cmd,
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
    elif system == "Darwin":  # macOS
        # Launch as detached background process (same approach as Linux)
        subprocess.Popen(
            [sys.executable] + cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    else:  # Linux
        # Launch as detached background process
        subprocess.Popen(
            [sys.executable] + cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    
    port_parts = []
    if serial_port:
        port_parts.append(f"serial={serial_port}")
    if tcp_port:
        port_parts.append(f"TCP={tcp_port}")
    port_msg = f" ({', '.join(port_parts)})" if port_parts else ""
    print(f"Launched ESP32 Remote Serial GUI on {system}{port_msg}")
    return 0


def main() -> int:
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="ESP32 Remote Serial Port Service - RFC2217 bridge GUI"
    )
    parser.add_argument(
        "--serial-port", "-s",
        type=str,
        default=None,
        help="Serial port to use (e.g., COM3, /dev/ttyUSB0). Pre-populates the serial port dropdown."
    )
    parser.add_argument(
        "--tcp-port", "-t",
        type=int,
        default=None,
        help="TCP port to use (e.g., 2217). When specified, prevents duplicate launches for this TCP port."
    )
    args = parser.parse_args()
    
    # Check if we're already the detached child process
    if os.environ.get("ESP_SERIAL_BRIDGE_DETACHED") == "1":
        # This is the actual GUI process - run normally
        pass
    else:
        # This is the initial call - check for existing instance if TCP port is specified
        if args.tcp_port and check_existing_instance(args.tcp_port):
            # Instance already running for this TCP port - skip launching
            return 0
        # No existing instance (or no TCP port specified) - detach and launch
        return launch_detached(args.serial_port, args.tcp_port)
    
    # Normal GUI launch (only reached by detached child)
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

    app = SerialPortPicker(initial_serial_port=args.serial_port, initial_tcp_port=args.tcp_port)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
