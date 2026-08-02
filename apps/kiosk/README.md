# PrintBar Kiosk Agent

The PrintBar Kiosk Agent is a Python service that runs on Raspberry Pi 5 units deployed at print kiosk locations. It connects to the PrintBar backend via WebSocket, receives print jobs, and controls a CUPS printer.

---

## System Requirements

| Requirement     | Specification              |
|-----------------|---------------------------|
| Hardware        | Raspberry Pi 5 (4GB RAM+) |
| OS              | Raspberry Pi OS Bookworm (64-bit) |
| Python          | 3.12+                     |
| Printer         | Any CUPS-compatible printer |
| Connectivity    | Ethernet (preferred) or WiFi |

---

## Setup on Raspberry Pi

### 1. Install System Dependencies

```bash
sudo apt-get update && sudo apt-get install -y \
    python3-pip python3-venv libcups2-dev cups cups-client
```

### 2. Add Pi User to lpadmin Group (for CUPS access)

```bash
sudo usermod -aG lpadmin pi
```

### 3. Deploy the Kiosk Agent

```bash
cd /opt
sudo git clone https://github.com/printbar/PrintBar-V1.git printbar-kiosk
cd printbar-kiosk/apps/kiosk
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure

```bash
cp config/kiosk.example.yaml config/kiosk.yaml
nano config/kiosk.yaml
```

Fill in:
- `kiosk_id`: UUID from admin dashboard (after registration)
- `api_key`: API key shown once at registration
- `backend_url`: Your PrintBar backend URL
- `cups_printer_name`: Run `lpstat -p` to find your printer name

### 5. Register the Kiosk via Admin Dashboard

POST to `/api/v1/kiosks/register` with admin credentials:

```json
{
  "name": "Main Campus Kiosk",
  "location": "Building A, Ground Floor",
  "city": "Mumbai"
}
```

Copy the `kioskId` and `apiKey` from the response into `kiosk.yaml`.

### 6. Install systemd Service

```bash
sudo cp systemd/printbar-kiosk.service /etc/systemd/system/
sudo useradd -m -r -s /bin/false printbar
sudo chown -R printbar:printbar /opt/printbar-kiosk
sudo systemctl daemon-reload
sudo systemctl enable printbar-kiosk
sudo systemctl start printbar-kiosk
```

### 7. Verify

```bash
sudo systemctl status printbar-kiosk
journalctl -u printbar-kiosk -f
```

---

## Configuration Reference

| Key | Description | Default |
|-----|-------------|---------|
| `kiosk_id` | UUID assigned at registration | Required |
| `api_key` | Raw API key from registration | Required |
| `name` | Human-readable kiosk name | PrintBar Kiosk |
| `backend_url` | PrintBar backend HTTPS URL | Required |
| `cups_printer_name` | CUPS printer name from `lpstat -p` | Required |
| `heartbeat_interval_sec` | Seconds between heartbeats | 30 |
| `temp_dir` | Temp directory for PDF downloads | /tmp/printbar |
| `log_dir` | Log file directory | /var/log/printbar |

---

## Environment Variable Overrides

All config values can be overridden with environment variables:

| Variable | Maps to |
|----------|---------|
| `KIOSK_ID` | `kiosk_id` |
| `KIOSK_API_KEY` | `api_key` |
| `BACKEND_URL` | `backend_url` |
| `CUPS_PRINTER` | `cups_printer_name` |

---

## Troubleshooting

### Kiosk won't connect

1. Check backend URL is reachable: `curl $BACKEND_URL/api/v1/health`
2. Verify API key is correct in `kiosk.yaml`
3. Check logs: `journalctl -u printbar-kiosk -n 100`

### Printer not found

```bash
lpstat -p           # List available printers
lpstat -d           # Show default printer
```

### PDF won't print

1. Test CUPS directly: `lp -d YOUR_PRINTER /tmp/test.pdf`
2. Check CUPS web interface: `http://localhost:631`

---

## Running in Docker (for testing)

```bash
docker build -t printbar-kiosk .
docker run \
  -e KIOSK_ID=your-uuid \
  -e KIOSK_API_KEY=your-key \
  -e BACKEND_URL=https://your-backend.com \
  printbar-kiosk
```
