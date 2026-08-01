PrintBar
Communication Protocol Specification

Version: 1.0

Status: Engineering Blueprint

Purpose

This document defines all communication protocols used throughout the PrintBar ecosystem.

It specifies:

REST API conventions
WebSocket protocol
Event contracts
Message schemas
Error handling
Request validation
Versioning
Retry policies
Timeouts
Correlation IDs
Idempotency

Every service must implement these standards exactly.

Communication Architecture
              Browser

                  │

              HTTPS REST

                  │

          FastAPI Backend

          │            │

     PostgreSQL    WebSocket Gateway

                         │

                  Secure WebSocket

                         │

                 Raspberry Pi Fleet
Communication Principles

All communication must satisfy:

TLS encrypted
Authenticated
Versioned
Logged
Validated
Observable
Backward compatible
Idempotent where required
Supported Protocols
Purpose	Protocol
Frontend → Backend	HTTPS REST
Backend → Frontend	WebSocket
Backend → Raspberry Pi	WebSocket
Raspberry Pi → Backend	WebSocket
Easebuzz → Backend	HTTPS Webhook
Internal Services	Python Service Layer (no HTTP)
REST API Standards

Every endpoint begins with

/api/v1/

Example

/api/v1/upload

/api/v1/payments

/api/v1/jobs

/api/v1/kiosks
HTTP Methods

GET

Read

POST

Create

PUT

Replace

PATCH

Partial Update

DELETE

Soft delete (where applicable)

Standard Request Headers
Content-Type: application/json

Accept: application/json

Authorization: Bearer <JWT>

X-Request-ID

X-Client-Version
Standard Response

Every successful response

{
  "success": true,
  "data": {},
  "message": "Operation successful.",
  "requestId": "uuid"
}

Error response

{
  "success": false,
  "error": {
    "code": "UPLOAD_001",
    "message": "Unsupported file type."
  },
  "requestId": "uuid"
}

Never expose stack traces.

Correlation ID

Every request generates

Request ID (UUID)

This ID propagates through:

Frontend

↓

Backend

↓

Database

↓

WebSocket

↓

Raspberry Pi

↓

Logs

This enables end-to-end tracing.

API Versioning

Current

v1

Future

v2

No breaking changes inside the same version.

Pagination

List endpoints use

{
  "page":1,
  "limit":20
}

Response

{
  "items":[],
  "page":1,
  "limit":20,
  "total":125
}
Validation

Every request validated using

Pydantic

Reject invalid payloads before business logic.

Time Format

ISO 8601 UTC

Example

2026-08-01T14:30:00Z

Never transmit local time.

UUID Format

All identifiers

UUID v4

Example

7fd8fd65-a2b2...
WebSocket Protocol

Transport

WSS

Never use plain WS.

WebSocket Connection Flow
Connect

↓

Authenticate

↓

Handshake

↓

Heartbeat

↓

Receive Events

↓

Reconnect
WebSocket Envelope

Every message follows

{
  "type":"",
  "version":"1.0",
  "timestamp":"",
  "messageId":"",
  "correlationId":"",
  "payload":{}
}

This structure is mandatory.

Message Types

Client

AUTH

PING

PONG

HEARTBEAT

ACK

ERROR

Server

NEW_JOB

CANCEL_JOB

JOB_STATUS

CONFIG_UPDATE

MAINTENANCE

SHUTDOWN
Example NEW_JOB
{
  "type":"NEW_JOB",
  "payload":{
      "jobId":"...",
      "downloadUrl":"...",
      "checksum":"..."
  }
}
ACK Message

Every critical command requires acknowledgement.

{
    "type":"ACK",
    "payload":{
        "messageId":"..."
    }
}

No ACK

↓

Retry

Heartbeat

Every

30 seconds

Example

{
  "type":"HEARTBEAT",
  "payload":{
      "cpu":32,
      "memory":41,
      "temperature":56,
      "printerStatus":"READY"
  }
}
Timeout Rules

REST

30 seconds

WebSocket heartbeat

30 seconds

ACK timeout

5 seconds

Download timeout

60 seconds

Print timeout

Configurable

Retry Strategy

REST

Network failures

↓

3 retries

Exponential backoff

WebSocket

Automatic reconnect

Delay

1s

2s

4s

8s

16s

30s max
Idempotency

Endpoints requiring idempotency

Payment Creation
Payment Verification
Print Job Creation
Webhook Processing

Every request uses

Idempotency-Key

Duplicate request

↓

Same response

Event Ordering

Messages include

sequenceNumber

Out-of-order events

↓

Discard

or

Request resync

Compression

Enable

gzip

for REST.

WebSocket compression optional.

File Downloads

Never transferred over WebSocket.

WebSocket only sends

Signed URL.

File downloaded through HTTPS.

Error Codes

Format

MODULE_NUMBER

Examples

UPLOAD_001

PAYMENT_002

PRINTER_005

KIOSK_010

Error catalog maintained separately.

Backward Compatibility

Unknown fields

↓

Ignore

Missing required fields

↓

Reject

This allows rolling upgrades.

Maintenance Mode

Server may broadcast

{
  "type":"MAINTENANCE"
}

Clients stop accepting new work and remain connected.

Shutdown Event

Graceful shutdown

{
  "type":"SHUTDOWN"
}

Kiosk:

finish current job
send completion
disconnect
Logging

Log

Request

Response

Latency

Retry

Disconnect

Reconnect

Timeout

ACK failures

Every log contains

Request ID
Correlation ID
Kiosk ID (if applicable)
Security

REST

JWT

HTTPS

WebSocket

JWT/API Key

TLS

Replay protection

Nonce

Timestamp

Rate limiting

Enabled

Performance Targets

REST

<200 ms

Heartbeat latency

<100 ms

Reconnect

<5 seconds

Message processing

<50 ms

AI Agent Rules

When implementing communication:

Use a single message envelope across all WebSocket traffic.
Separate transport concerns from business logic.
Keep REST APIs stateless.
Use correlation IDs for tracing.
Require ACKs for critical commands.
Never transfer binary files through WebSockets.
Validate every incoming message before processing.
Make retries safe through idempotency.
Definition of Done

Communication is complete only if:

REST APIs follow a consistent contract.
WebSocket messages use the standard envelope.
Authentication is enforced.
Correlation IDs are propagated.
ACK and retry mechanisms work.
Heartbeats are reliable.
Logging captures every interaction.
Unknown message types are handled gracefully.
Backward compatibility rules are respected.
End of Document