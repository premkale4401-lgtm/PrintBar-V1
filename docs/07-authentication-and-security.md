PrintBar
Authentication & Security Specification

Version: 1.0

Status: Engineering Blueprint

Purpose

This document defines the authentication model, authorization rules, security architecture, and operational security requirements for PrintBar.

Every component must follow this specification.

Security is not a separate module.

Security is a property of every module.

Security Philosophy

PrintBar follows Zero Trust Architecture.

Never trust:

Browser
Raspberry Pi
Frontend
API Client
Network
Uploaded File
Payment Callback

Every request must be authenticated.

Every action must be authorized.

Every input must be validated.

Security Principles

The platform follows:

Zero Trust
Principle of Least Privilege
Defense in Depth
Secure by Default
Fail Securely
Immutable Audit Logs
End-to-End Encryption
Complete Traceability
Identity Types

PrintBar contains four identities.

Guest User

↓

Admin

↓

Kiosk

↓

System

Each identity has different permissions.

Guest Users

Users are not required to create an account.

Instead, the backend creates a temporary Guest Session.

Guest sessions exist only for:

Upload
Payment
Print Status

Guest Session Object

{
  "sessionId": "...",
  "expiresAt": "...",
  "ipAddress": "...",
  "deviceFingerprint": "...",
  "createdAt": "..."
}

Guest sessions automatically expire.

Recommended expiration:

24 Hours
Session Security

Every session contains:

UUID
Random entropy
Creation timestamp
Expiration timestamp
IP hash
User-Agent hash

Never store plaintext fingerprints.

Hash them.

Authentication Methods
Component	Authentication
Browser	JWT
Admin	JWT + Refresh Token
Raspberry Pi	API Key + Mutual Authentication
Easebuzz	Signature Verification
Internal Services	Service Credentials
JWT Strategy

Access Token

15 Minutes

Refresh Token

30 Days

Access tokens should never be stored in LocalStorage.

Preferred:

HttpOnly Secure Cookie

JWT Claims

{
  "sub":"",
  "role":"",
  "sessionId":"",
  "exp":"",
  "iat":""
}
Refresh Tokens

Stored in database.

Never plaintext.

Store:

SHA256(token)

Support:

Rotation
Revocation
Expiration
Roles

Guest

Can

Upload
Pay
Track

Cannot

Access admin

Admin

Can

Dashboard
Reports
Pricing
Kiosks
Printers
Refunds

Kiosk

Can

Heartbeat
Download assigned jobs
Report printer status
Print jobs

Cannot

Read payments
Modify pricing
Access users
Raspberry Pi Authentication

Every kiosk receives:

Kiosk ID

API Key

API Key generated only once.

Stored hashed.

Never visible again.

Authentication Flow

Pi

↓

API Key

↓

Backend

↓

Verification

↓

JWT Session

↓

WebSocket Upgrade
API Key Rules

Length

64 Bytes

Random.

Cryptographically secure.

Rotate API Keys

Supported.

Old keys revoked immediately.

Mutual Authentication

Backend authenticates kiosk.

Kiosk authenticates backend.

Future:

TLS client certificates.

WebSocket Security

WebSocket upgrade only after authentication.

Every message includes:

{
  "timestamp":"",
  "messageId":"",
  "signature":"",
  "payload":{}
}

Reject:

Replay
Duplicate
Expired
Replay Protection

Every request includes

Nonce

Timestamp

Store nonce briefly in Redis.

Reject reuse.

Payment Security

Backend creates payment.

Frontend never creates payment.

Frontend never calculates price.

Payment Flow

Frontend

↓

Backend

↓

Easebuzz

↓

Webhook

↓

Verification

↓

Database

↓

Print Job
Easebuzz Webhook

Must verify:

Signature
Merchant Key
Transaction ID
Amount
Status

Never trust callback blindly.

Idempotency

Payment verification must be idempotent.

Same webhook twice

↓

Same result.

No duplicate print jobs.

File Upload Security

Every upload validated for:

Extension
MIME
Magic Bytes
Size
Encryption
Embedded JavaScript
Embedded Files
Corruption
Page Count

Future

Virus scanning.

Password Policy

Admin passwords

Minimum

16 Characters

Must include

Uppercase
Lowercase
Number
Special Character

Hash using:

Argon2id

Never SHA256.

Never MD5.

Never bcrypt for new deployments unless Argon2 is unavailable.

Secrets Management

Never commit:

.env

Production secrets stored in:

Railway/VPS secret manager
Docker secrets (future)
Cloud secret manager (future)
Encryption

Data In Transit

TLS 1.3

Data At Rest

Database encryption

Storage encryption

Never send secrets over HTTP.

CORS

Whitelist only.

Example

https://printbar.in

Never

*
CSP

Strict Content Security Policy.

Disallow:

Inline scripts
Unsafe eval
CSRF

Required for:

Admin panel
Cookie authentication

Not required for pure bearer-token APIs.

XSS Protection

Escape all output.

Sanitize user input.

Never trust filenames.

SQL Injection

Use SQLAlchemy ORM.

Parameterized queries only.

Never concatenate SQL strings.

SSRF Protection

Never allow backend to fetch arbitrary URLs supplied by users.

Only allow trusted domains when fetching external resources.

Rate Limiting

Guest

20 requests/minute

Upload

5 uploads/10 minutes

Payment

10 requests/hour

Admin Login

5 attempts/15 minutes

WebSocket

Message throttling enabled.

Brute Force Protection

After repeated failures:

Delay responses
Lock session temporarily
Alert logs
DDoS Protection

Cloudflare

↓

Rate Limiter

↓

Nginx

↓

FastAPI

Layered protection.

Audit Logs

Every security event logged.

Examples

Login
Logout
Upload
Payment
Print
Webhook
API Key Rotation
Admin Action

Audit logs are immutable.

Logging Rules

Never log:

Passwords
JWTs
API Keys
Payment Secrets
Full card information

Allowed:

Job ID
Session ID
Kiosk ID
Payment ID
Headers

Always send

Strict-Transport-Security

X-Frame-Options

X-Content-Type-Options

Referrer-Policy

Permissions-Policy

Content-Security-Policy
Dependency Security

Weekly dependency scan.

Automatic CVE alerts.

Pin versions.

No abandoned libraries.

Backup Security

Encrypted backups.

Access logged.

Restore tested quarterly.

Incident Response

Security incidents require:

Detection
Logging
Alert
Isolation
Recovery
Postmortem
Security Monitoring

Monitor:

Failed logins
Upload failures
Payment anomalies
Offline kiosks
WebSocket disconnects
Printer abuse
API abuse
Rate limit violations
AI Agent Rules

When implementing security:

Never trust client input.
Perform all business validation on the backend.
Keep secrets outside source control.
Authenticate every API.
Authorize every action.
Log every security event.
Use secure defaults.
Make operations idempotent where required.
Design every component assuming the network is hostile.
Prefer explicit allow-lists over block-lists.
Future Security Roadmap

The architecture should be ready to support:

Multi-factor authentication for admins
Hardware security keys (WebAuthn)
Mutual TLS for kiosks
Certificate pinning
HSM-backed secret management
SIEM integration
Automated anomaly detection
Geo-based access controls
Enterprise SSO (OIDC/SAML)
End of Document

This specification establishes the security baseline for PrintBar. Every future service—whether frontend, backend, payment integration, or Raspberry Pi client—must comply with these requirements.