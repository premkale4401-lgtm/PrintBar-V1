PrintBar
Database Design Specification

Version: 1.0

Status: Engineering Blueprint

Purpose

This document defines the canonical PostgreSQL database schema for PrintBar.

The database is the single source of truth for all persistent state in the platform.

All backend services, Raspberry Pi kiosks, payment processing, analytics, and future administrative tools must rely on this schema.

No service may introduce undocumented tables or modify existing tables without updating this specification.

Database Technology
Component	Technology
Database	PostgreSQL 16+
Provider	Supabase
ORM	SQLAlchemy 2.x
Migration	Alembic
Driver	asyncpg
Design Principles

The schema must satisfy:

Third Normal Form (3NF)
Strong referential integrity
UUID primary keys
Immutable audit history
Soft deletion where appropriate
Optimized indexing
Horizontal scalability
Minimal data duplication
ACID transactions
UUID Strategy

Every primary key shall use UUID v4.

Never use auto-increment IDs for business entities.

Example:

id = UUID
Naming Convention

Tables

snake_case
plural

Examples

users

kiosks

print_jobs

payments

uploaded_files

Columns

snake_case

Foreign Keys

user_id

payment_id

kiosk_id
Core Tables

The initial production database contains the following entities:

users

kiosks

printers

uploaded_files

print_jobs

payments

payment_webhooks

pricing_rules

heartbeat_logs

audit_logs

system_events

api_keys

refresh_tokens

Future tables

notifications

organizations

franchises

analytics

maintenance_logs

support_tickets
Entity Relationship Overview
User
 │
 │ 1
 │
 ▼
Uploaded Files
 │
 │ 1
 ▼
Print Jobs
 │
 ├──────────► Payment
 │
 ├──────────► Assigned Kiosk
 │
 └──────────► Printer

Kiosk
 │
 ├──────────► Heartbeats
 │
 └──────────► Printer

Payment
 │
 └──────────► Payment Webhooks

Everything
 │
 ▼
Audit Logs
Table: users

Purpose

Stores optional customer identity.

Although PrintBar is designed for guest printing, this table enables future features such as:

Order history
Loyalty
Campus login
Receipts
Enterprise accounts

Columns

id

email

phone

display_name

created_at

updated_at

Indexes

email

phone
Table: kiosks

Represents every deployed Raspberry Pi.

Columns

id

name

serial_number

api_key_hash

status

firmware_version

location

ip_address

last_seen

created_at

updated_at

Status Enum

ONLINE

OFFLINE

PRINTING

MAINTENANCE

ERROR

Indexes

status

serial_number

last_seen
Table: printers

Every kiosk has one printer initially.

Future:

Multiple printers.

Columns

id

kiosk_id

manufacturer

model

cups_name

connection_type

status

paper_level

toner_level

last_error

created_at

Status

READY

PRINTING

OFFLINE

PAPER_JAM

OUT_OF_PAPER

OUT_OF_TONER
Table: uploaded_files

Purpose

Stores uploaded document metadata.

Never store actual PDF bytes.

Files remain inside Supabase Storage.

Columns

id

storage_path

original_filename

mime_type

file_size

page_count

checksum_sha256

uploaded_at

expires_at

deleted_at

Indexes

checksum_sha256

uploaded_at
File Validation Metadata

Store

virus_scan

pdf_version

encrypted

password_protected

contains_javascript

contains_embedded_files

contains_forms

These fields allow future malware detection.

Table: print_jobs

This is the central business entity.

Columns

id

file_id

payment_id

kiosk_id

printer_id

copies

color_mode

paper_size

duplex

status

price

currency

created_at

started_at

completed_at
Print Status Enum
UPLOADED

VALIDATED

PAYMENT_PENDING

PAYMENT_SUCCESS

QUEUED

ASSIGNED

DOWNLOADING

READY_TO_PRINT

PRINTING

COMPLETED

FAILED

CANCELLED

PAYMENT_FAILED

DOWNLOAD_FAILED

State transitions must be validated in the service layer.

Table: payments

Stores all payment attempts.

Columns

id

gateway

gateway_transaction_id

order_id

amount

currency

status

signature_verified

payment_method

paid_at

created_at

Gateway

EASEBUZZ

Future

RAZORPAY

PHONEPE

STRIPE
Payment Status
PENDING

SUCCESS

FAILED

EXPIRED

REFUNDED
Table: payment_webhooks

Stores every webhook received.

Columns

id

payment_id

headers

payload

signature

verified

processed

received_at

Never delete webhook history.

Table: pricing_rules

Stores configurable pricing.

Example

BLACK_WHITE_PRICE

COLOR_PRICE

DUPLEX_PRICE

GST

DISCOUNT

Allows pricing updates without code changes.

Table: heartbeat_logs

Stores Raspberry Pi health.

Columns

id

kiosk_id

cpu_usage

memory_usage

disk_usage

temperature

printer_status

uptime

received_at

Retention

90 days

Table: audit_logs

Purpose

Immutable system history.

Columns

id

actor

entity_type

entity_id

action

previous_value

new_value

ip_address

timestamp

Never update.

Never delete.

Table: system_events

Stores internal events.

Examples

PaymentSucceeded

PrintStarted

PrinterOffline

PaperJam

WebhookFailed

KioskRegistered
Table: api_keys

Future

Third-party integrations.

Columns

id

name

hashed_key

permissions

expires_at

created_at
Table: refresh_tokens

JWT refresh tokens.

Columns

id

user_id

token_hash

expires_at

revoked_at

Never store plaintext tokens.

Soft Delete Strategy

Only business entities may use:

deleted_at TIMESTAMP

Audit logs

Payment history

Webhook history

must never be soft deleted.

Indexing Strategy

Always index

Foreign keys
Status columns
Created timestamps
Frequently queried fields

Composite indexes

Example

(status, created_at)

(kiosk_id, status)

(payment_id, status)
Constraints

Examples

Price

price >= 0

Copies

copies >= 1

Page count

page_count >= 1

Checksum

Unique

Storage path

Unique

Transactions

The following operations must execute within database transactions:

Payment verification
Print job creation
Job assignment
Refund processing
Kiosk registration
Data Retention Policy
Table	Retention
uploaded_files	30 days after completion (configurable)
print_jobs	5 years
payments	7 years
payment_webhooks	7 years
audit_logs	Never delete
heartbeat_logs	90 days
system_events	1 year
Backup Strategy
Daily automated backups
Point-in-time recovery enabled
Weekly backup verification
Quarterly restore drills

Backups must be encrypted at rest and in transit.

Migration Rules
All schema changes use Alembic.
No manual production database edits.
Every migration must be reversible where practical.
Seed data must be separated from schema migrations.
Performance Targets
Primary key lookups: < 10 ms
Indexed queries: < 50 ms
Complex dashboard queries: < 300 ms
Payment transaction commit: < 200 ms
Future Expansion

The schema is designed to support:

Multiple organizations
Franchise owners
Multi-tenant deployments
Multiple printers per kiosk
Dynamic pricing by location
Subscription plans
Coupons and promotions
AI-based analytics
Fleet management
International currencies
Multi-language support

without requiring a major redesign.

AI Agent Implementation Rules

When generating SQLAlchemy models:

One model per file.
Mirror this schema exactly.
Use UUID primary keys.
Use enums for status fields.
Add database constraints.
Add indexes as specified.
Generate Alembic migrations.
Avoid nullable fields unless justified.
Never store secrets or payment credentials in plaintext.
Keep business rules in the service layer, not in ORM models.
End of Document

This document defines the canonical data model for PrintBar. All future services, APIs, and integrations—including Easebuzz, Supabase Storage, and Raspberry Pi kiosks—must conform to this schema.