# ESP32 Remote Serial Service

A cross-platform GUI application that launches an `esp_rfc2217_server` instance, exposing a local serial port over TCP via the RFC 2217 protocol. This is especially useful for flashing and monitoring ESP32 devices from inside Docker dev containers or from remote machines.

## Prerequisites

- **Python 3.10+**
- A physical ESP32 device connected to a serial port on the host machine

## Setup

1. **Clone the repository**

   ```bash
   git clone <repo-url>
   cd esp-remote-serial
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   The application will also attempt to auto-install missing dependencies (`pyserial`, `esptool`) on first run.

## Usage

### Basic Usage

Run the service:

```bash
python3 esp-remote-serial.py
```

The script automatically launches the GUI as a **detached background process**, allowing the terminal command to return immediately without blocking. This is particularly useful when launching from build systems or container initialization scripts.

1. Select a serial port from the dropdown (click **Refresh** to re-scan).
2. Set the **TCP port** (default `2217`).
3. Click **Start** to launch the `esp_rfc2217_server`.
4. Click **Stop** to terminate the server.

The log panel at the bottom displays real-time output from the server process.

### Command-Line Arguments

You can pre-populate the GUI fields and enable duplicate-launch protection using command-line arguments:

```bash
python3 esp-remote-serial.py --serial-port COM3 --tcp-port 2217
```

**Available arguments:**

- `--serial-port` / `-s` - Pre-selects the specified serial port in the dropdown (e.g., `COM3`, `/dev/ttyUSB0`)
- `--tcp-port` / `-t` - Pre-fills the TCP port field and enables lock protection for that port

**Lock Behavior:**

When `--tcp-port` is specified, the script creates a lock file (`.esp-serial-tcp{port}.lock`) to prevent duplicate instances from being launched for the same TCP port. This is useful for automated launches (e.g., from dev container initialization) to avoid creating multiple instances.

- **With `--tcp-port`**: Checks for existing instance on that TCP port, skips launch if already running
- **Without `--tcp-port`**: Always launches a new instance (no lock protection)

**Examples:**

```bash
# Protected launch - won't create duplicate for TCP port 2217
python3 esp-remote-serial.py --tcp-port 2217

# Pre-populate both fields with lock protection
python3 esp-remote-serial.py --serial-port COM3 --tcp-port 2217

# Unprotected launch - always creates new instance
python3 esp-remote-serial.py
```

## Using from a VS Code Docker Dev Container

When developing inside a [Dev Container](https://code.visualstudio.com/docs/devcontainers/containers), the ESP32 device is physically attached to the **host** machine, not the container. The service bridges this gap by exposing the serial port over TCP.

### Host Setup

1. Run `esp-remote-serial.py` **on the host** (outside the container).
2. Select the correct serial port and click **Start**.

### Dev Container Configuration

Add the following to your VS Code **settings** (either `.devcontainer/devcontainer.json` or workspace `.vscode/settings.json` inside the container):

```jsonc
"customizations": {
   "vscode": {
      "settings": {
         "idf.port": "rfc2217://host.docker.internal:2217?ign_set_control"
      }
   }
}
```

- `host.docker.internal` resolves to the host machine from within the Docker container.
- `2217` matches the default TCP port in the service (adjust if you changed it).
- `ign_set_control` tells the client to ignore unsupported RFC 2217 control commands, avoiding errors with some ESP32 tooling.

With this configuration, the ESP-IDF extension (and any `esptool` / `idf.py` commands) inside the container will communicate with the ESP32 device on the host through the RFC 2217 tunnel.

### Automatic Launch from Dev Container

You can also configure your dev container to automatically launch the serial bridge on the host when the container starts. This eliminates the need to manually run the script each time.

1. **Add the script to your project:**

   You can either copy the script files or add this repository as a git submodule:

   **Option A: Copy the files**
   ```bash
   mkdir -p tools
   cp -r /path/to/esp-remote-serial tools/
   ```

   **Option B: Add as a git submodule**
   ```bash
   git submodule add <repo-url> tools/esp-remote-serial
   git submodule update --init --recursive
   ```

2. **Update your `.devcontainer/devcontainer.json`:**

   Add the `initializeCommand` property to automatically launch the GUI before the container starts:

   ```jsonc
   {
     "name": "Your Dev Container",
     "image": "your-image:latest",
     "initializeCommand": "python3 tools/esp-remote-serial/esp-remote-serial.py --tcp-port 2217",
     // ... other settings
   }
   ```

The `initializeCommand` runs **on the host machine** when the container is started, making it perfect for launching host-side services. Because the script launches as a detached background process, it won't block the container initialization process.

**Using `--tcp-port` in the `initializeCommand`** is recommended as it prevents duplicate instances from being created if you rebuild or restart the container multiple times. The lock mechanism ensures only one instance runs for each TCP port, while still allowing you to manually launch additional instances on different ports if needed.

## Accessing from Another Computer on Your Network

The service can be accessed from any computer on your local network, making it useful for remote development or sharing a single ESP32 device across multiple machines.

### Server Setup (Host Machine)

1. Run `esp-remote-serial.py` on the machine with the ESP32 connected.
2. Start the service as usual.
3. Find your host machine's IP address:
   - **Windows:** Run `ipconfig` and look for "IPv4 Address"
   - **macOS/Linux:** Run `ifconfig` or `ip addr` and look for your local network interface (usually starts with `192.168.x.x` or `10.x.x.x`)

The `esp_rfc2217_server` binds to `0.0.0.0` by default, making it accessible from any network interface.

### Client Configuration (Remote Machine)

Configure your client to connect using the host machine's IP address. For example:

**ESP-IDF Extension (VS Code settings.json):**
```jsonc
{
  "idf.port": "rfc2217://192.168.1.100:2217?ign_set_control"
}
```

**Command-line esptool:**
```bash
esptool.py --port rfc2217://192.168.1.100:2217?ign_set_control flash_id
```

Replace `192.168.1.100` with your host machine's actual IP address and `2217` with the TCP port configured in the GUI.

### Firewall Considerations

Ensure your firewall allows incoming connections on the TCP port (default `2217`):

- **Windows:** Add an inbound rule in Windows Defender Firewall
- **macOS:** Allow incoming connections in System Preferences → Security & Privacy → Firewall
- **Linux:** Configure `ufw` or `iptables` to allow the port

**Note:** This service does not include authentication. Only use it on trusted networks.
