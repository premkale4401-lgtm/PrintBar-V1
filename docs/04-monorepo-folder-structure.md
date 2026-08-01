PrintBar
Monorepo & Folder Structure

Version: 1.0

Status: Engineering Blueprint

Purpose

This document defines the official repository structure for PrintBar.

Every folder has a single responsibility.

No code should be placed in arbitrary locations.

The repository should remain understandable even after years of development.

Repository Overview
printbar/

├── apps/
│
├── packages/
│
├── infrastructure/
│
├── docker/
│
├── nginx/
│
├── scripts/
│
├── docs/
│
├── deployment/
│
├── .github/
│
├── .vscode/
│
├── .env.example
├── docker-compose.yml
├── Makefile
├── README.md
├── LICENSE
└── .gitignore
Philosophy

The repository is divided into four major areas.

Applications

Shared Packages

Infrastructure

Documentation

Applications should never contain infrastructure logic.

Infrastructure should never contain business logic.

apps/

Contains executable applications.

apps/

frontend/

backend/

kiosk/
apps/frontend/

Contains the existing Next.js frontend.

frontend/

app/

components/

hooks/

lib/

services/

store/

types/

styles/

assets/

public/

tests/
app/

Contains all routes.

Example

/

upload

pricing

payment

status

admin
components/

Reusable UI components.

buttons/

cards/

dialogs/

inputs/

layout/

navigation/

upload/

payment/

status/

Components must never directly call the database.

hooks/

Custom React hooks.

Example

useUpload()

usePayment()

useWebSocket()

usePrinterStatus()
lib/

Utilities.

axios.ts

config.ts

constants.ts

helpers.ts
services/

API layer.

Example

upload.service.ts

payment.service.ts

job.service.ts

websocket.service.ts

No UI logic.

store/

Global state.

Example

authStore

jobStore

uploadStore
types/

Shared frontend types.

apps/backend/

Production FastAPI backend.

backend/

app/

tests/

alembic/

requirements/

scripts/

Dockerfile
Backend Structure
app/

api/

core/

config/

models/

schemas/

repositories/

services/

workers/

payments/

uploads/

storage/

websocket/

kiosk/

printer/

middleware/

security/

utils/

events/

dependencies/
api/

Only HTTP endpoints.

No business logic.

Example

payment.py

upload.py

jobs.py

health.py

kiosk.py
services/

Contains business logic.

Example

PaymentService

UploadService

PricingService

PrintJobService

KioskService
repositories/

Database access only.

Never business logic.

Example

PaymentRepository

JobRepository

UserRepository
models/

SQLAlchemy models.

One model per file.

schemas/

Pydantic models.

Separate:

Request

Response

Internal
workers/

Background processing.

Example

pdf_processing.py

cleanup.py

retry_jobs.py
storage/

Everything related to Supabase Storage.

payments/

Easebuzz integration.

Contains

gateway.py

signature.py

webhook.py

refund.py
kiosk/

Kiosk management.

Contains

registration.py

heartbeat.py

authentication.py

job_dispatch.py
printer/

Printing abstraction.

Future support

Brother

HP

Canon

Generic CUPS

middleware/

HTTP middleware.

Examples

Logging

Rate Limiting

Request ID

Security Headers

Authentication
security/

Security utilities.

Contains

JWT

Hashing

Encryption

Token Verification

Permissions
utils/

Pure helper functions.

No side effects.

dependencies/

FastAPI dependency injection.

events/

Internal event bus.

Examples

PaymentCompleted

JobCreated

PrintStarted

PrintFinished
apps/kiosk/

Production Raspberry Pi software.

kiosk/

app/

config/

downloads/

logs/

systemd/

tests/

requirements.txt

Dockerfile
Kiosk Structure
app/

client/

printer/

storage/

heartbeat/

authentication/

jobs/

websocket/

config/

logging/

utils/
client/

Main application.

websocket/

Persistent WebSocket client.

printer/

CUPS wrapper.

Example

print.py

status.py

queue.py
jobs/

Handles

Receive

Download

Print

Complete

Retry

heartbeat/

Sends heartbeat every 30 seconds.

logs/

Rolling log files.

packages/

Shared code.

packages/

sdk/

types/

shared/
sdk/

Future SDK.

Used by

Frontend

Backend

Admin

types/

Shared TypeScript interfaces.

Example

PrintJob

Payment

Kiosk

Printer

Upload
shared/

Constants.

Enums.

Utilities.

Validation.

infrastructure/

Infrastructure configuration.

infrastructure/

terraform/

monitoring/

prometheus/

grafana/

Future-ready.

docker/

Contains Docker files.

frontend/

backend/

kiosk/
nginx/
default.conf

ssl.conf

security.conf
deployment/

Deployment scripts.

production/

staging/

development/
scripts/

Automation.

setup.sh

backup.sh

restore.sh

deploy.sh

cleanup.sh
docs/

Contains all engineering documentation.

01-product-vision.md

02-system-architecture.md

03-tech-stack-and-engineering-standards.md

04-monorepo-folder-structure.md

...
.github/

GitHub configuration.

workflows/

ISSUE_TEMPLATE/

PULL_REQUEST_TEMPLATE/
workflows/

Examples

test.yml

lint.yml

build.yml

deploy.yml
Root Files
README.md

Project overview.

LICENSE

License.

docker-compose.yml

Local development stack.

Makefile

Developer shortcuts.

Example

make dev

make build

make lint

make test

make migrate

make seed

make clean
.env.example

Contains every required environment variable.

Never commit real secrets.

File Organization Rules

Each file should ideally remain under 300–500 lines.

If a file exceeds 500 lines, consider splitting it by responsibility.

One class per file where practical.

Avoid "utility dumping grounds" or files that mix unrelated concerns.

Import Rules

Allowed:

API

↓

Services

↓

Repositories

↓

Database

Not allowed:

API

↓

Database

All business logic must pass through the service layer.

Dependency Rules
Frontend

↓

REST API

↓

Services

↓

Repositories

↓

Database

The Raspberry Pi communicates only with the backend via authenticated APIs/WebSockets and never accesses the database directly.

AI Agent Rules

When creating new code:

Respect the folder structure.
Do not create duplicate modules.
Prefer extending existing services over adding parallel implementations.
Do not place business logic in controllers, UI components, or repositories.
Keep modules cohesive and independently testable.
Document any new top-level directory before introducing it.
Repository Growth Strategy

The structure should comfortably support:

100+ backend modules
1,000+ React components
Hundreds of Raspberry Pi kiosks
Multiple payment providers
Multiple printer vendors
Multiple deployment environments
Additional mobile applications
White-label deployments
Enterprise customer customization

without requiring a repository redesign.

End of Document

This document defines the canonical repository layout for PrintBar. Any future feature or service must fit into this structure without compromising clarity or maintainability.