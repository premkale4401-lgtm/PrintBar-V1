# PrintBar Backend — Disaster Recovery Procedures

This document outlines standard operating procedures (SOPs) for recovering from common production failures.

## 1. Database Connectivity Loss

**Symptom:**
- API returns `500 Internal Server Error` with `SYS_000`.
- Logs show `sqlalchemy.exc.OperationalError` or `Connection refused`.

**Recovery:**
1. Check Supabase Dashboard (or Postgres host) to verify database is running.
2. Verify `DATABASE_URL` environment variable is correct.
3. Check network connectivity between backend container and database.
4. Restart backend container to re-establish connection pools:
   ```bash
   docker-compose restart backend
   ```

## 2. Invalid or Expired JWT Secret

**Symptom:**
- Valid sessions are suddenly rejected (`401 Unauthorized`).
- Logs show `jwt.exceptions.DecodeError`.

**Recovery:**
1. Check `JWT_SECRET` environment variable. Ensure it has not been changed inadvertently.
2. If the secret was rotated:
   - All active user sessions are invalidated. Users will need to start new kiosk sessions.
   - All admin refresh tokens are invalidated. Admins must log in again.
3. Apply correct `JWT_SECRET` and restart backend.

## 3. Webhook Failures (Payment Gateway)

**Symptom:**
- Webhook signature validation fails (`PAY_001` in logs).
- Webhook logs show `webhook_endpoint_signature_rejected`.

**Recovery:**
1. Check `WEBHOOK_SECRET` environment variable against the Payment Gateway Dashboard.
2. Verify the gateway is configured to send the correct payload format.
3. If signatures continue to fail, generate a new webhook secret in the gateway and update `.env`. Restart backend.

## 4. Redis/Rate Limiter Failure

**Symptom:**
- Currently, rate limiting uses in-memory storage (slowapi default). If Redis is introduced and fails, API endpoints might hang or return 500 errors.

**Recovery:**
1. Check Redis status: `docker ps | grep redis`.
2. Restart Redis container: `docker-compose restart redis`.
3. If issue persists, temporarily disable rate-limiting by removing `app.add_middleware(SlowAPIMiddleware)` in `main.py` until Redis is restored (requires redeployment).

## 5. Storage / Supabase Timeout

**Symptom:**
- File uploads fail with timeout errors.
- Print kiosks fail to download files (`STORAGE_ERROR` in logs).

**Recovery:**
1. Verify Supabase Storage status via Supabase Dashboard.
2. Verify `SUPABASE_SERVICE_ROLE_KEY` is valid and has not expired.
3. Check `SUPABASE_URL`.
4. If Supabase is down, kiosks will queue jobs until storage is restored.

## 6. Corrupted Migration State

**Symptom:**
- App fails to start with `Alembic` errors in logs.

**Recovery:**
1. Check current migration state:
   ```bash
   docker-compose exec backend alembic current
   ```
2. Re-apply missing migrations:
   ```bash
   docker-compose exec backend alembic upgrade head
   ```
3. If state is completely desynchronized, you may need to stamp the database (Use with caution!):
   ```bash
   docker-compose exec backend alembic stamp head
   ```
