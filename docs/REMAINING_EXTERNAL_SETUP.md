# PrintBar V1 — Remaining External Setup Guide

**Date:** 2026-08-03  
**Purpose:** Everything that must happen OUTSIDE the codebase before going live.

> **The codebase is COMPLETE. No further software development is required.**
> All items below are operational/configuration tasks only.

---

## 1. Backend Hosting

### Option A — Docker (Recommended)
```bash
# On your server/VPS:
git clone https://github.com/YOUR_ORG/PrintBar.git
cd PrintBar

# Copy and fill environment file
cp .env.example .env
nano .env

# Start all services
docker compose up -d

# Run database migrations
docker compose exec backend alembic upgrade head

# Seed initial admin user
docker compose exec backend python scripts/seed_db.py
```

### Option B — Supabase (Database Only)
- Create project at supabase.com
- Copy connection string to `DATABASE_URL`
- Copy project URL and service role key to `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY`
- Create storage buckets: `print-files`, `receipts`, `reports`, `system-assets`
- Set all buckets to **PRIVATE**

---

## 2. Environment Variables to Fill

### Required (No Defaults)
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/printbar
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...
JWT_SECRET=<128-char random string>
WS_SECRET=<64-char random string>
```

Generate secrets:
```bash
python -c "import secrets; print(secrets.token_hex(64))"
```

### Payment (Currently Mock — Replace When Ready)
```bash
PAYMENT_PROVIDER=razorpay          # Change from 'mock'
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
```

Configure webhook in Razorpay Dashboard:
- URL: `https://your-domain.com/api/v1/payments/webhook/razorpay`
- Events: `payment.captured`, `payment.failed`

### CORS (Update for Production Domain)
```bash
ALLOWED_ORIGINS=https://printbar.in,https://www.printbar.in
```

---

## 3. Razorpay Account Setup

1. Create account at razorpay.com
2. Complete KYC verification (required for live payments)
3. Go to Settings → API Keys → Generate Live Key
4. Copy Key ID and Key Secret to `.env`
5. Go to Settings → Webhooks → Add Webhook
6. Set URL to `https://api.printbar.in/api/v1/payments/webhook/razorpay`
7. Copy Webhook Signing Secret to `.env`
8. Set `PAYMENT_PROVIDER=razorpay` in `.env`

---

## 4. Initial Admin User

```bash
# Inside the running backend container or venv:
python scripts/seed_db.py \
  --email admin@printbar.in \
  --password "ChangeMe123!" \
  --name "PrintBar Admin" \
  --role SUPER_ADMIN
```

Login at: `https://printbar.in/admin`

---

## 5. Initial Pricing Rule

After logging in to the admin dashboard:
1. Go to **Settings** tab
2. Set B&W price per page (default ₹2.00)
3. Set Color price per page (default ₹10.00)
4. Set GST % (default 18%)
5. Click **Save Settings**

Or via API:
```bash
curl -X POST https://api.printbar.in/api/v1/admin/pricing \
  -H "Authorization: Bearer YOUR_ADMIN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Standard 2026",
    "bwPriceInr": "2.00",
    "colorPriceInr": "10.00",
    "a3Multiplier": "1.75",
    "gstPercent": "18.00"
  }'
```

---

## 6. Register First Kiosk

```bash
curl -X POST https://api.printbar.in/api/v1/admin/kiosks \
  -H "Authorization: Bearer YOUR_SUPER_ADMIN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Hub 1 - Main Branch",
    "location": "Ground Floor, City Mall",
    "city": "Hyderabad"
  }'
```

**The API key is returned ONCE. Copy it immediately into `kiosk.yaml`.**

---

## 7. SSL/TLS

Use Nginx + Certbot:
```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.printbar.in -d printbar.in
```

Or use Cloudflare proxy (simplest).

---

## 8. Raspberry Pi Setup

See: `docs/PRINTER_READINESS_REPORT.md` for the complete checklist.

**Summary:**
1. Install Raspberry Pi OS Lite
2. Install CUPS + printer driver
3. Register printer with CUPS
4. Deploy kiosk agent with `kiosk.yaml`
5. Start `printbar-kiosk` systemd service

---

## Summary Checklist

- [ ] Server/VPS provisioned
- [ ] Docker Compose running
- [ ] Database migrations applied (`alembic upgrade head`)
- [ ] Environment variables set
- [ ] Supabase storage buckets created and set to PRIVATE
- [ ] Initial admin user seeded
- [ ] Initial pricing rule created
- [ ] SSL/TLS configured
- [ ] Razorpay KYC complete (when ready)
- [ ] Razorpay live credentials injected
- [ ] Razorpay webhook configured
- [ ] First kiosk registered and API key stored
- [ ] Raspberry Pi setup complete (per PRINTER_READINESS_REPORT.md)
- [ ] Test print job verified end-to-end

**Estimated time to go live: 3–4 hours (assuming credentials ready)**
