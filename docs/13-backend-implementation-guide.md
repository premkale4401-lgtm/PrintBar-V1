PrintBar
Backend Implementation Guide

Version: 1.0

Status: Implementation Guide

Purpose

This document defines the implementation strategy for the PrintBar backend.

It specifies:

Project architecture
Folder structure
Coding standards
Dependency injection
Service boundaries
Repository pattern
Implementation phases
Development workflow
Testing strategy

This document is the authoritative guide for implementing the FastAPI backend.

Technology Stack
Component	Technology
Language	Python 3.12+
Framework	FastAPI
ORM	SQLAlchemy 2.x
Validation	Pydantic v2
Database	PostgreSQL
Storage	Supabase Storage
Authentication	JWT
Payments	Easebuzz
Realtime	WebSockets
Cache	Redis
Printing	Raspberry Pi
Development Philosophy

The backend must follow:

Clean Architecture
SOLID Principles
Dependency Injection
Repository Pattern
Service Pattern
Event-Driven Design
Domain-Oriented Design

Business logic must never depend on frameworks.

Backend Folder Structure
backend/

app/

    api/

        v1/

            upload.py

            payment.py

            jobs.py

            kiosk.py

            printer.py

            health.py

    core/

        config.py

        logging.py

        security.py

        constants.py

    database/

        base.py

        session.py

        migrations/

    models/

    schemas/

    repositories/

    services/

    websocket/

    events/

    middleware/

    storage/

    payments/

    kiosk/

    printer/

    workers/

    dependencies/

    exceptions/

    utils/

tests/

Dockerfile

requirements.txt

alembic.ini
Layered Architecture
REST API

↓

Services

↓

Repositories

↓

Database

No shortcuts.

Controllers never access SQLAlchemy directly.

Controller Layer

Responsibilities

Parse requests
Validate input
Call service
Return response

Must NOT

Query database
Calculate pricing
Handle payments
Print documents

Controllers should ideally remain under 150 lines.

Service Layer

Contains all business logic.

Examples

UploadService

PaymentService

PricingService

PrintJobService

KioskService

PrinterService

Services coordinate repositories and external integrations.

Repository Layer

Repositories perform only persistence operations.

Example

PaymentRepository

create()

update()

find_by_id()

find_by_transaction()

list()

No business rules.

Database Models

Each SQLAlchemy model lives in its own file.

Example

models/

payment.py

print_job.py

kiosk.py

uploaded_file.py

Relationships are defined explicitly.

Schema Layer

Separate request and response models.

Example

schemas/

payment/

    request.py

    response.py

upload/

    request.py

    response.py

Never expose ORM models directly.

Dependency Injection

Use FastAPI dependencies.

Example

def get_payment_service() -> PaymentService:
    ...

Avoid global state and singletons where possible.

Event-Driven Design

Business events should be emitted for significant actions.

Examples

PaymentSucceeded

JobCreated

JobAssigned

PrintStarted

PrintCompleted

PrinterOffline

Consumers react to events without tightly coupling modules.

Error Handling

Define custom exceptions.

Example

PaymentNotFoundError

InvalidPDFError

PrinterOfflineError

KioskNotRegisteredError

Map exceptions to standardized API responses.

Logging

Structured JSON logging.

Every log entry includes:

Timestamp
Request ID
Correlation ID
Session ID (if applicable)
Kiosk ID (if applicable)
Severity
Module

Never log secrets or sensitive payloads.

Configuration

Use pydantic-settings.

Environment variables only.

No hardcoded credentials.

Support:

Development
Staging
Production
Background Tasks

Use FastAPI background tasks initially.

Future migration path:

Celery
Redis Queue

Suitable tasks:

Cleanup
Expired uploads
Metrics aggregation
Notifications
WebSocket Gateway

Separate module.

Responsibilities:

Authentication
Connection lifecycle
Heartbeats
Event dispatch
Retry handling

No business logic.

Payment Integration

Encapsulate Easebuzz behind a gateway interface.

class PaymentGateway:
    def create_order(...)
    def verify_payment(...)
    def refund(...)

Never reference Easebuzz directly outside the payment module.

Storage Integration

Storage service responsibilities:

Upload
Download
Signed URLs
Delete
Metadata synchronization

No controller should interact with Supabase Storage directly.

Raspberry Pi Integration

Dedicated kiosk module.

Responsibilities:

Registration
Authentication
Heartbeats
Job dispatch
Status updates

Communication only through defined services and WebSocket gateway.

Middleware

Global middleware should include:

Request ID
Logging
Security headers
Rate limiting
Exception handling
CORS

Keep middleware independent of business logic.

Testing Strategy

Every module requires:

Unit tests
Integration tests

Critical flows additionally require:

End-to-end tests

Target:

≥85% code coverage
Implementation Phases
Phase 1

Foundation

FastAPI project
Config
Logging
Database
Docker
Health endpoints
Phase 2

Uploads

Validation
Storage
Metadata
Cleanup
Phase 3

Pricing

Pricing engine
Business rules
Phase 4

Payments

Easebuzz integration
Webhooks
Idempotency
Phase 5

Print Jobs

State machine
Assignment
Status updates
Phase 6

Raspberry Pi

Registration
WebSockets
Heartbeats
Dispatch
Phase 7

Admin

Dashboard
Analytics
Management APIs
Phase 8

Production

Monitoring
Metrics
Security hardening
Performance tuning
Coding Rules
Keep functions focused.
Prefer composition over inheritance.
Use async I/O where appropriate.
Avoid circular dependencies.
Document public interfaces.
Enforce typing throughout.
Prefer explicitness over clever abstractions.
AI Agent Rules

When implementing the backend:

Follow the architecture documents exactly.
Do not invent undocumented modules.
Keep controllers thin.
Keep services cohesive.
Use dependency injection consistently.
Generate tests alongside implementation.
Preserve backward compatibility.
Avoid changing the existing frontend unless integration requires it.
Write production-ready code with clear documentation.
Definition of Done

A backend module is complete only if:

Architecture is respected.
API endpoints implemented.
Validation complete.
Tests passing.
Logging present.
Documentation updated.
Security review completed.
Docker build succeeds.
Performance targets met.
End of Document