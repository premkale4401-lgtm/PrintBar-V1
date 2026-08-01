PrintBar
REST API Specification

Version: 1.0

Status: Engineering Blueprint

Purpose

This document defines every REST API exposed by the PrintBar backend.

Every endpoint includes:

Route
Method
Authentication
Validation
Business Rules
Request Schema
Response Schema
Error Codes
Rate Limits
Permissions

The API is the only interface between the frontend and backend.

No frontend component shall access the database directly.

API Principles

The API must satisfy:

RESTful
Stateless
Versioned
Secure
Idempotent
Observable
Fully documented
OpenAPI compliant
Base URL
https://api.printbar.in/api/v1
Authentication Matrix
Endpoint	Auth Required
Upload	Guest Session
Payment	Guest Session
Status	Guest Session
Admin	Admin JWT
Kiosk	API Key
Health	None
API Modules
Health

Authentication

Uploads

Payments

Print Jobs

Pricing

Kiosks

Printers

Admin

Monitoring

System
Standard Success Response
{
  "success": true,
  "message": "",
  "data": {},
  "requestId": ""
}
Standard Error Response
{
  "success": false,
  "error": {
      "code": "UPLOAD_001",
      "message": "Unsupported file."
  },
  "requestId":""
}
Health APIs
GET /health

Purpose

Simple liveness check.

Authentication

None

Response

{
    "status":"healthy"
}
GET /ready

Readiness probe.

Checks

Database
Storage
Redis
WebSocket Gateway
GET /live

Container liveness.

Used by Docker.

Session APIs
POST /session

Creates guest session.

Request

{}

Response

{
    "sessionId":"",
    "expiresAt":""
}

Business Rules

Always generate UUID
Expires after 24 hours
DELETE /session

Invalidate session.

Upload APIs
POST /uploads

Purpose

Upload PDF.

Authentication

Guest Session

Request

Multipart Form

Validation

PDF only
≤25MB
Not encrypted
Valid MIME
Valid magic bytes

Response

{
    "fileId":"",
    "pages":12
}

Errors

UPLOAD_001

UPLOAD_002

UPLOAD_003
GET /uploads/{id}

Returns metadata.

Never returns file.

DELETE /uploads/{id}

Deletes upload.

Allowed only before payment.

Pricing APIs
POST /pricing/calculate

Request

{
    "fileId":"",
    "copies":2,
    "color":"BW"
}

Backend computes

price
tax
total

Frontend never computes.

Response

{
    "subtotal":60,
    "gst":12,
    "total":72
}
Payment APIs
POST /payments/create

Purpose

Create Easebuzz order.

Request

{
    "fileId":"",
    "copies":2,
    "color":"BW"
}

Response

{
    "paymentId":"",
    "paymentUrl":"..."
}
POST /payments/webhook

Called only by Easebuzz.

Authentication

Signature Verification

Never by browser.

GET /payments/{id}

Returns

Current payment state.

POST /payments/refund

Admin only.

Future.

Print Job APIs
POST /jobs

Creates print job.

Internal use only.

Never exposed directly.

GET /jobs/{id}

Returns

{
    "status":"PRINTING",
    "progress":42
}
GET /jobs

Admin only.

Supports

pagination
filters
search
DELETE /jobs/{id}

Cancel.

Allowed

Only before printing.

Kiosk APIs
POST /kiosks/register

Purpose

Register Raspberry Pi.

Authentication

Provisioning Key

Response

{
    "kioskId":"",
    "apiKey":""
}
POST /kiosks/auth

Authenticate kiosk.

Returns

JWT.

POST /kiosks/heartbeat

Called every

30 seconds.

Request

{
    "cpu":42,
    "memory":31,
    "temperature":54,
    "printer":"READY"
}
GET /kiosks

Admin only.

Returns

All kiosks.

GET /kiosks/{id}

Returns

Detailed health.

PATCH /kiosks/{id}

Maintenance Mode.

Rename.

Disable.

Printer APIs
GET /printers

Returns

Printer list.

GET /printers/{id}

Returns

Printer status.

POST /printers/test-print

Admin only.

Prints

Test page.

PATCH /printers/{id}

Update

Configuration.

Admin APIs
POST /admin/login

Returns

JWT

Refresh Token

POST /admin/logout

Revokes

Refresh Token.

GET /admin/dashboard

Returns

Statistics.

GET /admin/analytics

Future.

GET /admin/audit

Audit logs.

GET /admin/payments

Payment history.

GET /admin/jobs

Job history.

GET /admin/users

Future.

Monitoring APIs
GET /metrics

Prometheus.

GET /system/status

Returns

Database
Redis
Storage
Queue
Active kiosks
Search APIs

Future

GET /search/jobs

GET /search/payments

GET /search/kiosks
Pagination

Standard

?page=1

&limit=20
Filtering

Examples

status=PRINTING

payment=SUCCESS

kiosk=001
Sorting
sort=created_at

order=desc
Status Codes
200 OK

201 Created

202 Accepted

204 No Content

400 Bad Request

401 Unauthorized

403 Forbidden

404 Not Found

409 Conflict

422 Validation Error

429 Too Many Requests

500 Internal Server Error
Validation Rules

Every endpoint validates

UUIDs
Enums
Numbers
Length
Required fields

Reject invalid requests before business logic.

Rate Limits

Guest

60 req/min

Upload

5 uploads/10 min

Admin

120 req/min

Kiosk

120 heartbeat/min
API Documentation

FastAPI shall automatically generate

Swagger UI

Redoc

OpenAPI JSON

Available only in

Development

or

Protected Admin environments.

OpenAPI Rules

Every endpoint requires

Summary
Description
Tags
Examples
Response Models
Error Models

No undocumented endpoint is allowed.

Logging

Every request logs

Request ID
Session ID
User ID
Kiosk ID
Duration
Status Code
IP Address
API Deprecation

Deprecated endpoints remain available for at least one major release.

Responses should include:

Deprecation: true
Sunset: <date>

where applicable.

AI Agent Rules

When implementing the REST API:

Follow this specification exactly.
Keep controllers thin; delegate business logic to services.
Validate every request using Pydantic.
Return standardized success and error responses.
Never expose database models directly.
Use dependency injection for authentication, authorization, and shared services.
Generate comprehensive OpenAPI documentation.
Preserve the existing frontend and integrate these endpoints without changing the UI.
Definition of Done

The REST API is complete only if:

Every documented endpoint is implemented.
OpenAPI documentation is generated.
Validation is enforced.
Authentication and authorization are applied correctly.
Rate limiting is active.
Logging and metrics are in place.
Integration tests pass for every endpoint.
API responses conform to the standard schema.
End of Document