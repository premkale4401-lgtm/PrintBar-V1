# PrintBar Testing Strategy

## Overview

PrintBar follows a multi-layer testing strategy. No feature is complete without corresponding tests.

---

## Test Pyramid

```
         /\
        /E2E\       End-to-end (future: Playwright)
       /------\
      /  Integ  \   Integration tests (FastAPI + SQLite)
     /------------\
    /  Unit Tests  \ Unit tests (repositories, services, utils)
   /----------------\
```

---

## Backend Tests (apps/backend/tests/)

### Tools
- **pytest** with **pytest-asyncio** (async test support)
- **httpx.AsyncClient** with **ASGITransport** (in-process HTTP testing)
- **SQLite + aiosqlite** (in-memory DB for tests, no Postgres required)
- **unittest.mock** for external service mocking

### Test Files

| File | Coverage |
|------|----------|
| `test_health.py` | `/health` endpoint |
| `test_session.py` | Guest session creation, JWT validation |
| `test_upload.py` | File upload validation, storage mocking |
| `test_pricing.py` | Pricing calculation, all paper sizes, duplex |
| `test_payment_gateway.py` | Payment provider protocol |
| `test_dev_payment.py` | Mock payment flow |
| `test_mock_payment.py` | End-to-end mock payment flow |
| `test_admin.py` | Admin endpoint auth guards |
| `test_webhook.py` | Webhook signature validation |
| `test_kiosks.py` | Kiosk HTTP endpoints |

### Running Tests

```bash
cd apps/backend
.venv/Scripts/python -m pytest tests/ -v
```

With coverage:
```bash
.venv/Scripts/python -m pytest tests/ --cov=app --cov-report=html
```

### Key Patterns

1. **All DB calls use the test SQLite session** — never hit real Postgres.
2. **Storage calls are mocked** via `mock_storage` fixture.
3. **Background workers are patched out** — tests are synchronous.
4. **No real HTTP calls** — httpx transport uses in-process ASGI.

---

## Kiosk Agent Tests (apps/kiosk/tests/)

### Tools
- **pytest** with **pytest-asyncio**
- **unittest.mock** for CUPS, httpx, websockets

### Test Files

| File | Coverage |
|------|----------|
| `test_heartbeat.py` | HeartbeatSender message format and timing |
| `test_downloader.py` | PDF download, SHA-256 verification, retry |
| `test_printer.py` | CupsAdapter status, job submission |

### Running Kiosk Tests

```bash
cd apps/kiosk
pip install -r requirements.txt pytest pytest-asyncio
pytest tests/ -v
```

---

## Coverage Targets

| Component | Target |
|-----------|--------|
| Backend API layer | >80% |
| Backend services | >85% |
| Backend repositories | >75% |
| Kiosk agent core | >70% |

---

## CI Integration

Tests run automatically via GitHub Actions:
- On every push to `main` and `develop`
- On every pull request to `main`
- Backend tests: `.github/workflows/backend-test.yml`
- Lint: `.github/workflows/lint.yml`

---

## What We Do NOT Test

- Real Supabase storage calls (mocked)
- Real payment gateway (mocked via MockPaymentProvider)
- Real CUPS hardware (mocked via pycups mock)
- Real WebSocket connections from Pi hardware (integration tested at deployment)
