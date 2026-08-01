PrintBar
Deployment & DevOps Architecture

Version: 1.0

Status: Production Engineering Specification

Purpose

This document defines the complete deployment architecture for PrintBar.

It specifies:

Infrastructure
CI/CD
Docker
Nginx
Production environments
Monitoring
Scaling
Secrets
Security
Release process

The deployment architecture must support reliable operation across hundreds of Raspberry Pi kiosks.

Infrastructure Philosophy

PrintBar follows a Cloud + Edge architecture.

Business logic lives in the cloud.

Printing happens at the edge.

Every Raspberry Pi is an edge node.

The cloud remains the single source of truth.

High-Level Infrastructure
Users

↓

Cloudflare

↓

Nginx

↓

FastAPI Backend

↓

Redis

↓

PostgreSQL

↓

Supabase Storage

↓

WebSocket Gateway

↓

Raspberry Pi Fleet
Deployment Environments

Three environments are mandatory.

Development

↓

Staging

↓

Production

Each environment must have isolated resources.

Development

Purpose

Local development.

Contains

Docker Compose
Mock services
Debug logging
Swagger enabled

Never use production credentials.

Staging

Purpose

Pre-production validation.

Contains

Production-like infrastructure
Real integrations
Test payment credentials
Test Raspberry Pi

Used before every production deployment.

Production

Purpose

Customer traffic.

Requirements

HTTPS only
Monitoring enabled
Backups enabled
Secrets managed
Rate limiting
High availability
Deployment Architecture
GitHub

↓

GitHub Actions

↓

Docker Build

↓

Container Registry

↓

Production Server

↓

Docker Compose

↓

Nginx

↓

FastAPI
Docker

Every service must have its own image.

Containers

Frontend

Backend

Redis

Nginx

Future

Celery

Prometheus

Grafana
Docker Rules

Containers must be

Stateless
Immutable
Restartable
Health Checked

Never store uploads inside containers.

Docker Compose

Development stack

frontend

backend

postgres

redis

nginx

Production

PostgreSQL may be managed by Supabase.

Reverse Proxy

Use

Nginx

Responsibilities

SSL termination
Compression
Rate limiting
Security headers
Static assets
Reverse proxy
WebSocket upgrade
HTTPS

Mandatory.

TLS 1.3

Redirect

HTTP

↓

HTTPS

Domain Structure

Example

printbar.in

www.printbar.in

api.printbar.in

admin.printbar.in

Future

kiosk.printbar.in

status.printbar.in

docs.printbar.in
Environment Variables

Separate

Development

Staging

Production

Never reuse secrets.

Secret Management

Secrets include

JWT_SECRET

DATABASE_URL

SUPABASE_KEY

SUPABASE_SERVICE_ROLE_KEY

EASEBUZZ_KEY

EASEBUZZ_SALT

REDIS_URL

Never commit secrets.

Never expose secrets to frontend.

CI/CD Pipeline
Push

↓

Lint

↓

Unit Tests

↓

Build

↓

Security Scan

↓

Docker Build

↓

Deploy Staging

↓

Integration Tests

↓

Manual Approval

↓

Deploy Production

Production deployments require approval.

Branch Strategy
main

develop

feature/*

hotfix/*

Only main deploys to production.

Deployment Strategy

Preferred

Blue-Green Deployment

Future

Canary Releases

Avoid downtime.

Rollback Strategy

Every deployment creates

Docker image tag
Git tag
Release notes

Rollback should take less than 5 minutes.

Health Checks

Backend

/health

/ready

/live

Containers restart automatically on failure.

Auto Restart

Docker

restart: unless-stopped

Raspberry Pi

systemd

Restart=always
RestartSec=5
Logging

All services write structured JSON logs.

Logs include

Timestamp
Service
Level
Request ID
Correlation ID

No sensitive information.

Monitoring

Collect metrics for

API latency
Error rate
Payment success
Print success
Active kiosks
Printer health
Storage usage

Future

Prometheus + Grafana.

Alerting

Critical alerts

Backend offline
Database unavailable
Redis unavailable
Payment failures
Kiosk offline
Printer offline
Storage quota exceeded

Future integrations

Email
Slack
Discord
PagerDuty
Database Migrations

Use Alembic.

Rules

Every schema change is a migration.
Migrations are version controlled.
No manual production edits.
Static Assets

Served through

Next.js

or

CDN.

Never through FastAPI.

Caching

Use Redis for

Sessions
Rate limits
WebSocket state
Temporary data

Never cache payment verification.

WebSocket Deployment

Nginx must support

Upgrade headers
Long-lived connections
Sticky sessions (if needed)
Backup Strategy

Database

Daily backups
Point-in-time recovery

Storage

Bucket versioning (future)
Lifecycle rules

Configuration

Git
Infrastructure as Code
Disaster Recovery

Target RPO

≤15 minutes

Target RTO

≤30 minutes

Scaling Strategy

Phase 1

1 backend
1 kiosk

Phase 2

Multiple kiosks
Multiple printers

Phase 3

Horizontal backend scaling
Redis-backed WebSockets
Distributed workers

Phase 4

Multi-region deployment
Multi-tenant support

No redesign should be required between phases.

Infrastructure Security

Mandatory

Cloudflare WAF
HTTPS
Security headers
Rate limiting
Secret rotation
Firewall
Minimal open ports
Automatic security updates
Release Checklist

Before production deployment:

Tests pass
Security scan passes
Docker builds
Database migrations reviewed
Documentation updated
Rollback verified
Monitoring configured
AI Agent Rules

When implementing deployment:

Containerize every service.
Keep containers stateless.
Never hardcode secrets.
Use Docker Compose for local development.
Prepare for Kubernetes without depending on it.
Support zero-downtime deployments.
Preserve WebSocket connectivity through Nginx.
Ensure deployments are reproducible.
Definition of Done

Deployment architecture is complete only if:

Development, staging, and production environments exist.
CI/CD is automated.
Docker images are reproducible.
HTTPS is enforced.
Health checks work.
Rollbacks are possible.
Monitoring and logging are active.
Secrets are managed securely.
The platform can be deployed consistently without manual configuration drift.
End of Document