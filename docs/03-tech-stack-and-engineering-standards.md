PrintBar
Tech Stack & Engineering Standards

Version: 1.0

Status: Engineering Blueprint

Purpose

This document defines the official technology stack, engineering standards, coding conventions, architectural rules, and development practices for the PrintBar platform.

Every developer, AI coding agent, and contributor must follow this specification. No implementation should deviate unless the architecture document is updated.

Engineering Philosophy

PrintBar is designed as a production-grade SaaS + Edge Computing platform, not a prototype.

Every decision should prioritize:

Reliability
Security
Scalability
Maintainability
Performance
Observability
Developer Experience

The platform must be capable of operating 24×7 across hundreds of unattended kiosks.

Official Technology Stack
Frontend
Technology	Version	Purpose
Next.js	Latest Stable	Web Application
React	Latest Stable	UI Framework
TypeScript	Latest Stable	Type Safety
Tailwind CSS	Latest Stable	Styling
shadcn/ui	Latest Stable	UI Components
Framer Motion	Latest Stable	Animations
React Hook Form	Latest Stable	Forms
Zod	Latest Stable	Validation
TanStack Query	Latest Stable	API State
Axios	Latest Stable	HTTP Client
Backend
Technology	Version	Purpose
Python	3.12+	Runtime
FastAPI	Latest Stable	REST API
Uvicorn	Latest Stable	ASGI Server
SQLAlchemy 2.x	Latest Stable	ORM
Alembic	Latest Stable	Migrations
Pydantic v2	Latest Stable	Validation
httpx	Latest Stable	Async HTTP
WebSockets	Native	Realtime
Celery (future)	Latest Stable	Background Tasks
Database
Technology	Purpose
PostgreSQL	Primary Database
Supabase	Managed PostgreSQL
Redis	Cache + Queue
Supabase Storage	File Storage
Raspberry Pi
Technology	Purpose
Raspberry Pi OS Lite 64-bit	Operating System
Python	Kiosk Client
CUPS	Printing
WebSocket Client	Communication
systemd	Process Management
Infrastructure
Technology	Purpose
Docker	Containerization
Docker Compose	Local Development
Nginx	Reverse Proxy
Cloudflare	CDN + WAF
GitHub Actions	CI/CD
Prometheus (future)	Metrics
Grafana (future)	Monitoring
Architecture Style

PrintBar follows Clean Architecture.

Presentation Layer

↓

Application Layer

↓

Domain Layer

↓

Infrastructure Layer

Dependencies always point inward.

The Domain Layer must not depend on any external framework.

SOLID Principles

Every module must comply with:

Single Responsibility Principle

One class = One responsibility.

Example:

PaymentService

Handles payments only.

Not

PaymentService

Payment

+

Emails

+

Database

+

Logging
Open Closed Principle

New features should extend existing code instead of modifying stable components.

Liskov Substitution

Interfaces must be replaceable without changing behavior.

Interface Segregation

Small focused interfaces.

Avoid "God Interfaces."

Dependency Inversion

Business logic depends only on abstractions.

Never directly instantiate infrastructure services.

Example:

# Good
class PaymentService:
    def __init__(self, payment_gateway: PaymentGateway):
        self.gateway = payment_gateway
Clean Folder Structure

Backend

backend/

app/

api/

core/

config/

models/

schemas/

repositories/

services/

workers/

websocket/

storage/

payments/

kiosk/

printer/

utils/

tests/

Every folder has one responsibility.

Naming Standards
Variables
print_job
payment_status
user_session

Never:

a
b
temp
abc
Classes

Use PascalCase

PaymentService

PrintJobRepository

KioskManager
Functions

snake_case

create_payment()

verify_signature()

download_pdf()
Constants
MAX_FILE_SIZE_MB

PAYMENT_TIMEOUT

SUPPORTED_FILE_TYPES
Files

snake_case

payment_service.py

print_queue.py

kiosk_client.py
Dependency Injection

Never instantiate dependencies inside business logic.

Wrong

payment = Easebuzz()

Correct

payment = PaymentGateway()

Injected through constructors or FastAPI dependency injection.

Configuration Management

Never hardcode:

API keys
URLs
Secrets
Credentials

Everything comes from:

.env

Environment variables only.

Environment Variables

Example

DATABASE_URL

SUPABASE_URL

SUPABASE_KEY

EASEBUZZ_KEY

EASEBUZZ_SALT

JWT_SECRET

STORAGE_BUCKET

WS_SECRET

REDIS_URL

Never commit .env files.

Logging Standards

Never use:

print()

Use structured logging.

Example

logger.info()

logger.warning()

logger.error()

logger.exception()

Every log should include:

Timestamp
Request ID
User ID (if available)
Kiosk ID (if available)
Job ID (if available)
Error Handling

Never expose stack traces.

Bad

{
  "error": "Traceback..."
}

Good

{
  "success": false,
  "message": "Payment verification failed."
}

Internal details go to logs.

API Standards

RESTful.

Versioned.

Example

/api/v1/uploads

/api/v1/payments

/api/v1/jobs

/api/v1/kiosks

No breaking changes inside a version.

Validation

All incoming data must be validated.

Use:

Pydantic
Zod

Never trust frontend data.

Git Standards

Branch naming

feature/payment

feature/uploads

bugfix/websocket

hotfix/payment-timeout

Commit messages

feat:

fix:

docs:

refactor:

test:

chore:
Code Documentation

Every public class must have:

Purpose
Parameters
Return values
Exceptions

Complex algorithms require inline explanations.

Testing Standards

Minimum requirements:

Unit Tests
Integration Tests
API Tests

Critical modules additionally require:

Payment Tests
Upload Tests
Security Tests
WebSocket Tests

Target code coverage:

≥ 85%

Performance Standards

API Response Time

Target:

< 200 ms

Upload Validation

< 2 sec

Payment Verification

< 5 sec

WebSocket Latency

< 100 ms

Security Standards

Mandatory:

HTTPS only
JWT authentication
Signed URLs
Parameterized SQL
Input validation
Output encoding
CSRF protection (where applicable)
Rate limiting
CORS restrictions
Secure cookies
Secret rotation
Audit logging

No sensitive data in logs.

Documentation Standards

Every new module must include:

README (if complex)
API documentation
Sequence diagrams (where useful)
Configuration examples
Error reference
AI Agent Implementation Rules

When implementing PrintBar:

Preserve the existing frontend design.
Never rewrite the UI unless explicitly instructed.
Replace mock data with production APIs.
Keep business logic exclusively in the backend.
Avoid monolithic services.
Prefer modular, testable components.
Write self-documenting code.
Follow Clean Architecture and SOLID.
Do not introduce unnecessary dependencies.
Optimize for long-term maintainability over short-term speed.
Definition of Done (DoD)

A feature is considered complete only if:

Business logic implemented
Validation added
Tests written and passing
Logging included
Error handling implemented
API documented
Security reviewed
No linting issues
No type errors
Performance verified
Ready for production deployment
End of Document

This document is the engineering constitution for PrintBar. Every future implementation—whether by humans or AI—must adhere to these standards to ensure the codebase remains consistent, secure, and production-ready.