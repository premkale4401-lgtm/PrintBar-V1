# PrintBar V1 — Test Summary

**Date:** 2026-08-03  
**Total Tests:** 102  
**Passing:** 102  
**Failing:** 0  
**Coverage Target:** 85%

---

## Test Files

| File | Tests | Description |
|---|---|---|
| `test_session.py` | 8 | Guest session creation, JWT token, delete |
| `test_upload.py` | 12 | PDF validator (extension, MIME, magic bytes, size, pages), upload endpoint |
| `test_pricing.py` | 13 | PricingService `_compute` unit tests, endpoint integration |
| `test_pricing_service.py` | 8 | PriceCalculation dataclass, BW/COLOR pricing with real DB |
| `test_payment.py` | 18 | Mock payment flow: create order, verify, poll, webhook |
| `test_webhook.py` | 3 | Webhook 404 in mock mode, missing signature rejection, dev complete |
| `test_admin.py` | 18 | Auth guards for all admin endpoints, error schema validation, pricing endpoint |
| `test_storage.py` | 14 | SHA-256, object path, upload/retry/error, signed URL, delete |
| `test_jobs.py` | 8 | Job status endpoint (existing) |

---

## Test Strategy

**Unit Tests (no DB, no network):**
- `TestPricingServiceCompute` — pure `_compute()` method with mock `PricingRule`
- `StorageService` methods — httpx mocked with `AsyncMock`
- `PriceCalculation.to_dict()` — pure Python dataclass

**Integration Tests (SQLite in-memory DB):**
- Session creation → JWT token → upload auth
- Payment flow: create order → verify signature → webhook processing
- Pricing service with real DB rule fixture
- Admin endpoint auth guards

**Fixture Design:**
- `setup_test_database` — session-scoped, creates SQLite tables once, tears down at end
- `db_session` — function-scoped, rolls back after each test (isolation)
- `async_client` — function-scoped HTTPX test client with dependency override
- `mock_storage` — mocks Supabase Storage to prevent real network calls

---

## How to Run

```bash
cd apps/backend
.venv/Scripts/python -m pytest tests/ -v
```

**With coverage:**
```bash
.venv/Scripts/python -m pytest tests/ --cov=app --cov-report=term-missing
```

**Single file:**
```bash
.venv/Scripts/python -m pytest tests/test_payment.py -v
```

---

## Previously Failing Tests (Fixed)

| Test | Root Cause | Fix |
|---|---|---|
| `test_compute_sha256_returns_hex_string` | Wrong hardcoded hash value | Corrected to actual SHA-256("hello world") |
| `test_admin_401_response_structure` | Checked FastAPI `detail` key; PrintBar uses custom error schema | Updated assertion to check `success/error/code` |
| `test_pricing_endpoint_returns_list_structure` | Wrong URL (`/api/v1/pricing` → 404) | Fixed to `/api/v1/pricing/calculate` |
| `test_calculate_bw_a4` | `RuntimeError` propagated through ASGI transport | Added `try/except` in pricing endpoint |
| All 79 original tests (ScopeMismatch) | `asyncio_default_fixture_loop_scope=function` conflicted with session-scoped fixture | Changed to `session` scope |
