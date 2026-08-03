# PrintBar V1 — Printer Readiness Report

**Date:** 2026-08-03  
**Target Hardware:** Raspberry Pi 5 + USB Printer (CUPS-managed)

---

## Architecture Overview

```
Raspberry Pi 5
  └── PrintBar Kiosk Agent (apps/kiosk/)
        ├── auth/           — API key authentication with backend
        ├── client/         — HTTP client for job download
        ├── heartbeat/      — 30-second health metric sender
        ├── jobs/           — Job state machine handler
        ├── printer/        — CUPS adapter (lp command wrapper)
        ├── monitoring/     — CPU/RAM/disk/temperature metrics
        └── websocket/      — WebSocket connection to backend
```

---

## CUPS Integration Status

| Component | File | Status |
|---|---|---|
| CUPS command wrapper | `apps/kiosk/app/printer/cups_adapter.py` | IMPLEMENTED |
| Signed URL downloader | `apps/kiosk/app/client/downloader.py` | IMPLEMENTED |
| Job state machine | `apps/kiosk/app/jobs/handler.py` | IMPLEMENTED |
| Print options builder | `apps/kiosk/app/printer/options.py` | IMPLEMENTED |
| Heartbeat sender | `apps/kiosk/app/heartbeat/sender.py` | IMPLEMENTED |
| WebSocket client | `apps/kiosk/app/websocket/client.py` | IMPLEMENTED |

---

## Raspberry Pi Physical Setup Checklist

### 1. Operating System
- [ ] Install Raspberry Pi OS Lite (64-bit, Bookworm) — headless
- [ ] Enable SSH: create empty `ssh` file in `/boot/firmware/`
- [ ] Set hostname: `printbar-kiosk-01`

### 2. Network
- [ ] Connect to WiFi or Ethernet
- [ ] Note the IP address for SSH access

### 3. CUPS Installation
```bash
sudo apt-get update
sudo apt-get install -y cups cups-client
sudo systemctl enable cups
sudo systemctl start cups
sudo usermod -aG lpadmin pi
```

### 4. Printer Driver
```bash
# For HP printers:
sudo apt-get install -y hplip

# For Epson printers:
sudo apt-get install -y printer-driver-escpr

# For Canon printers:
# Download driver from Canon website
```

### 5. Printer Registration in CUPS
```bash
# Access CUPS web interface
http://localhost:631

# Or via command line:
lpinfo -v                          # list detected printers
lpadmin -p PrintBar -E \
  -v usb://HP/LaserJet%20P1606dn \
  -m drv:///sample.drv/generic.ppd \
  -D "PrintBar Printer"
lpadmin -d PrintBar                # set as default
```

### 6. Kiosk Agent Deployment
```bash
# Clone repository
git clone https://github.com/YOUR_ORG/PrintBar.git
cd PrintBar/apps/kiosk

# Install Python dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure kiosk
cp config/kiosk.yaml.example config/kiosk.yaml
nano config/kiosk.yaml  # Fill in kiosk_id, api_key, backend_url

# Install systemd service
sudo cp systemd/printbar-kiosk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable printbar-kiosk
sudo systemctl start printbar-kiosk
```

### 7. kiosk.yaml Required Fields
```yaml
backend_url: "https://api.printbar.in"
kiosk_id: "YOUR_KIOSK_UUID"      # From POST /admin/kiosks response
api_key: "YOUR_KIOSK_API_KEY"    # From POST /admin/kiosks response (shown once)
printer_name: "PrintBar"          # CUPS printer name
log_level: "info"
```

---

## Print Job Flow (End to End)

1. Guest uploads PDF → Backend validates → Stores in Supabase
2. Guest selects options → Backend calculates price → Guest pays
3. Backend marks job `QUEUED` → Dispatches to kiosk via WebSocket
4. Kiosk receives job via WebSocket `print_job` message
5. Kiosk downloads PDF via signed URL (5-minute expiry)
6. Kiosk sends `lp -d PrintBar -o sides=one-sided -o ColorModel=Gray file.pdf`
7. Kiosk polls `lpstat -p PrintBar` to detect completion
8. Kiosk sends `{"type": "job_update", "status": "COMPLETED"}` to backend
9. Backend marks job `COMPLETED`, deletes file from storage

---

## CUPS Command Reference

```bash
# Check printer status
lpstat -p PrintBar

# Print test page
lp -d PrintBar /usr/share/cups/data/testprint

# Check print queue
lpq -P PrintBar

# Cancel all jobs
cancel -a PrintBar

# View CUPS error log
sudo journalctl -u cups -f
```

---

## Known Printer Codes

| CUPS State | Kiosk Action |
|---|---|
| `idle` | Printer ready |
| `printing` | Job in progress |
| `stopped` | Report as OFFLINE, retry after 30s |
| `disabled` | Mark printer as error, alert operator |

---

## Estimated Setup Time

| Task | Time |
|---|---|
| OS install + SSH | 15 min |
| CUPS install + driver | 20 min |
| Printer registration | 10 min |
| Kiosk agent deploy | 15 min |
| Test print | 5 min |
| **Total** | **~65 min** |
