PrintBar
Complete System Architecture

Version: 1.0

Status: Engineering Blueprint

Purpose

This document defines the complete architecture of the PrintBar platform.

It establishes:

System boundaries
Component responsibilities
Communication protocols
Data flow
Deployment topology
Service interactions
Scalability strategy

No implementation should violate the architecture described in this document.

High-Level System
                         ┌─────────────────────────────┐
                         │         End Users           │
                         │  Mobile / Laptop Browser    │
                         └─────────────┬───────────────┘
                                       │
                                   HTTPS (TLS)
                                       │
                                       ▼
                        ┌─────────────────────────────┐
                        │        Cloudflare CDN       │
                        │ DDoS Protection + DNS + WAF │
                        └─────────────┬───────────────┘
                                      │
                                      ▼
                        ┌─────────────────────────────┐
                        │      Nginx Reverse Proxy    │
                        └─────────────┬───────────────┘
                                      │
             ┌────────────────────────┴────────────────────────┐
             │                                                 │
             ▼                                                 ▼
   Next.js Frontend                                FastAPI Backend
                                                     REST + WebSocket
                                                             │
               ┌─────────────────────────────────────────────┼────────────────────────────┐
               │                                             │                            │
               ▼                                             ▼                            ▼
        PostgreSQL (Supabase)                   Supabase Storage                    Redis Cache
               │                                                                          │
               └──────────────────────────────┬───────────────────────────────────────────┘
                                              │
                                              ▼
                                      Job Orchestrator
                                              │
                                              ▼
                                 Raspberry Pi WebSocket Fleet
                                              │
                                              ▼
                                        USB Laser Printer
Major Components
1. Frontend

Technology

Next.js
TypeScript
TailwindCSS
shadcn/ui

Responsibilities

QR landing page
Upload UI
Print settings
Price display
Easebuzz checkout
Live job status
Error handling
Progress indicators

Frontend SHALL NOT

calculate pricing
verify payments
create print jobs
trust user inputs
communicate directly with Raspberry Pi
2. Backend (Core)

Technology

FastAPI
Python 3.12+
AsyncIO

Responsibilities

Business logic
Authentication
Validation
Payment integration
Job scheduling
WebSockets
Printer orchestration
Audit logging
API

The backend is the brain of PrintBar.

Every business decision happens here.

3. PostgreSQL

Responsibilities

users
kiosks
print jobs
payments
printers
pricing
logs
sessions
webhooks
analytics

Database never stores files.

Only metadata.

4. Supabase Storage

Stores

PDFs
Receipts
Generated reports

Never exposed publicly.

Files accessed using

Signed URLs.

5. Redis

Purpose

WebSocket state
Heartbeats
Job queues
Rate limiting
Cache
Temporary sessions

Redis should never become the source of truth.

6. Raspberry Pi Fleet

Every kiosk runs

printbar-kiosk

Responsibilities

Register with backend
Authenticate
Maintain WebSocket
Download PDF
Print
Send progress
Send heartbeat
Monitor printer

Never handles

payments
pricing
user information
database
Deployment Topology
Internet

↓

Cloudflare

↓

Nginx

↓

FastAPI

↓

PostgreSQL

↓

Supabase Storage

↓

Redis

↓

Kiosk Fleet
Backend Modules

The backend is divided into independent modules.

API

Authentication

Payments

Uploads

Pricing

Print Jobs

Kiosk Manager

Printer Manager

WebSocket Gateway

Storage

Notifications

Monitoring

Audit Logs

Each module owns its own business logic.

Modules communicate through service interfaces.

Communication
Browser → Backend

Protocol

HTTPS

Payload

JSON

Authentication

JWT

Backend → Database

Protocol

SQLAlchemy ORM

Async

Backend → Storage

Protocol

Supabase SDK

Backend → Raspberry Pi

Protocol

Secure WebSocket

Realtime

Bidirectional

Raspberry Pi → Printer

Protocol

USB

CUPS

Job Lifecycle
Upload

↓

Validation

↓

Price Calculation

↓

Payment

↓

Verification

↓

Create Job

↓

Queue

↓

Assign Kiosk

↓

Download PDF

↓

Print

↓

Completion

↓

Archive

Every transition updates the database.

Print Job States
UPLOADED

↓

VALIDATED

↓

PAYMENT_PENDING

↓

PAYMENT_SUCCESS

↓

QUEUED

↓

DOWNLOADING

↓

READY_TO_PRINT

↓

PRINTING

↓

COMPLETED

Failure states

FAILED

CANCELLED

PAYMENT_FAILED

DOWNLOAD_FAILED

PRINTER_OFFLINE

PAPER_JAM

OUT_OF_PAPER

State transitions must be immutable and fully logged.

Kiosk Lifecycle
BOOT

↓

REGISTER

↓

AUTHENTICATE

↓

HEARTBEAT

↓

IDLE

↓

JOB_RECEIVED

↓

PRINTING

↓

IDLE
Heartbeat System

Every Raspberry Pi sends

{
  kioskId,
  printerStatus,
  paperLevel,
  tonerLevel,
  cpu,
  memory,
  temperature,
  uptime,
  timestamp
}

every 30 seconds.

Missing heartbeats for more than 90 seconds marks the kiosk as Offline.

Scalability

Current Target

1 Backend
10 Kiosks
100 Users

Future

1000+ kiosks
Multi-region
Auto scaling
Load balancing
Horizontal workers
Distributed queues

No architectural redesign should be required to reach these milestones.

Failure Recovery

The system must gracefully recover from:

Backend restart
Raspberry Pi reboot
Printer disconnect
Network outage
Payment webhook delay
Storage outage
Redis restart

All critical operations must be idempotent.

Logging

Every service logs:

Requests
Responses
Errors
Exceptions
State changes
Print events
Payments
Authentication
WebSocket events

Logs must be structured JSON for compatibility with centralized logging systems.

Monitoring

Health endpoints

/health

/ready

/live

Metrics

CPU
Memory
Database latency
Queue depth
Active kiosks
Jobs/minute
Payment success rate
Printer uptime
Engineering Rules

The architecture must satisfy the following constraints:

Frontend remains the presentation layer only.
Backend is the single source of truth.
Raspberry Pi functions only as an execution agent.
All business logic resides in the backend.
No component communicates directly with another component unless explicitly defined in this architecture.
All inter-service communication must be authenticated, encrypted, and logged.
Every feature must be designed for horizontal scalability and operational resilience.
Notes for Antigravity

When implementing this architecture:

Do not redesign or replace the existing frontend.
Preserve the current UI, animations, layout, routing, and user experience.
Replace mock data with real backend integrations.
Build new functionality as modular services that integrate cleanly with the existing frontend.