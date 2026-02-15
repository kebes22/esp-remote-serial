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

Run the service:

```bash
python esp-remote-serial.py
```

1. Select a serial port from the dropdown (click **Refresh** to re-scan).
2. Set the **TCP port** (default `2217`).
3. Click **Start** to launch the `esp_rfc2217_server`.
4. Click **Stop** to terminate the server.

The log panel at the bottom displays real-time output from the server process.

## Using from a VS Code Docker Dev Container

When developing inside a [Dev Container](https://code.visualstudio.com/docs/devcontainers/containers), the ESP32 device is physically attached to the **host** machine, not the container. The service bridges this gap by exposing the serial port over TCP.

### Host Setup

1. Run `esp-remote-serial.py` **on the host** (outside the container).
2. Select the correct serial port and click **Start**.

### Dev Container Configuration

Add the following to your VS Code **settings** (either `.devcontainer/devcontainer.json` or workspace `.vscode/settings.json` inside the container):

```jsonc
{
  "idf.port": "rfc2217://host.docker.internal:2217?ign_set_control"
}
```

- `host.docker.internal` resolves to the host machine from within the Docker container.
- `2217` matches the default TCP port in the service (adjust if you changed it).
- `ign_set_control` tells the client to ignore unsupported RFC 2217 control commands, avoiding errors with some ESP32 tooling.

With this configuration, the ESP-IDF extension (and any `esptool` / `idf.py` commands) inside the container will communicate with the ESP32 device on the host through the RFC 2217 tunnel.
