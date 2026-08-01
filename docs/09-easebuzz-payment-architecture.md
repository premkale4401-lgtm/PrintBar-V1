PrintBar
Easebuzz Payment Architecture Specification

Version: 1.0

Status: Engineering Blueprint

Purpose

This document defines the complete payment architecture for PrintBar using Easebuzz as the initial payment gateway.

The payment system must be:

Secure
Idempotent
Auditable
Gateway-independent
Fault tolerant
Horizontally scalable

The backend shall be the only authority for payment processing.

Payment Philosophy

The frontend never:

Calculates the amount
Creates payment orders
Verifies payment
Trusts redirect URLs
Marks payments as successful

The frontend only displays payment status.

All financial decisions belong to the backend.

Payment Architecture
Browser
    │
    ▼
Frontend
    │
    ▼
FastAPI Payment Service
    │
    ▼
Easebuzz
    │
    ▼
Webhook
    │
    ▼
Payment Verification
    │
    ▼
Database
    │
    ▼
Print Job Service
Payment Components

The payment module consists of:

Payment API

↓

Pricing Service

↓

Order Service

↓

Easebuzz Gateway

↓

Webhook Handler

↓

Signature Validator

↓

Payment Verifier

↓

Print Job Trigger

Each component has a single responsibility.

Folder Structure
payments/

gateway.py

easebuzz.py

pricing.py

webhook.py

signature.py

refund.py

exceptions.py

models.py

schemas.py

service.py
Payment Lifecycle
Print Settings Selected

↓

Price Calculation

↓

Payment Order Created

↓

Pending

↓

Easebuzz Checkout

↓

Webhook Received

↓

Signature Verified

↓

Transaction Verified

↓

Payment Success

↓

Print Job Created

↓

Archived
Payment State Machine
CREATED

↓

PENDING

↓

PROCESSING

↓

SUCCESS

↓

FAILED

↓

EXPIRED

↓

REFUNDED

Allowed transitions only.

Never jump directly between unrelated states.

Payment Object

Every payment stores

Payment ID

Gateway

Gateway Order ID

Gateway Transaction ID

Amount

Currency

Status

Signature Verified

Created At

Updated At

Paid At
Order Creation Flow
User

↓

Select Print Settings

↓

Backend

↓

Calculate Price

↓

Create Payment Record

↓

Create Easebuzz Order

↓

Return Payment URL

↓

Frontend Redirect
Price Locking

Price is calculated exactly once.

After order creation:

Pricing changes must not affect the order.
Taxes remain fixed.
Discounts remain fixed.

The stored amount becomes immutable.

Supported Currency

Initial

INR

Future-ready for:

USD
EUR
GBP
Easebuzz Integration

The gateway layer must expose a common interface.

Example:

class PaymentGateway:

    create_order()

    verify_payment()

    refund()

    verify_webhook()

Easebuzz implements this interface.

Future gateways implement the same interface.

Business logic never depends directly on Easebuzz.

Order Creation Rules

The backend must generate:

Internal Payment ID
Internal Order ID

Never use gateway IDs as primary identifiers.

Redirect Flow
Frontend

↓

Backend

↓

Easebuzz Checkout

↓

Success/Failure Redirect

↓

Frontend Status Page

The redirect page is informational only.

It never confirms payment.

Webhook Flow
Easebuzz

↓

Webhook Endpoint

↓

Signature Verification

↓

Transaction Verification

↓

Database Update

↓

Print Job Creation

↓

WebSocket Notification
Signature Verification

Every webhook must verify:

Merchant Key
Signature
Amount
Transaction ID
Order ID

Failure

↓

Reject immediately.

Never trust unsigned requests.

Idempotency

Every webhook contains a unique transaction reference.

Rules:

Same webhook 1 time → Process
Same webhook 10 times → Ignore duplicates
Same webhook after restart → Ignore duplicates

No duplicate print jobs.

No duplicate payments.

Payment Verification

Success requires:

Signature valid
Merchant key valid
Amount matches
Currency matches
Transaction successful
Order exists
Payment still pending

Only then:

Payment Status

↓

SUCCESS
Failure Handling

Possible failures:

Payment Failed

Payment Cancelled

Payment Expired

Signature Invalid

Order Not Found

Amount Mismatch

Gateway Error

Network Timeout

Each failure receives a unique error code.

Timeout Rules

Payment timeout

15 Minutes

Expired orders

↓

EXPIRED

Cannot be reused.

Print Job Creation

Print jobs are created only after:

Payment Status = SUCCESS

Never before.

Refund Architecture

Future support:

Full Refund
Partial Refund
Automatic Refund
Manual Refund

Refunds must create new database records.

Never modify the original payment.

Payment Ledger

Every financial event is immutable.

Examples:

Order Created

Payment Initiated

Webhook Received

Signature Verified

Payment Successful

Refund Requested

Refund Completed

Ledger entries are append-only.

Database Transactions

The following actions occur in one transaction:

Verify Payment

↓

Update Payment

↓

Create Print Job

↓

Create Audit Log

↓

Commit

If any step fails:

Rollback everything.

Security Requirements

Mandatory:

HTTPS only
Signed requests
Backend verification
Idempotency
Replay protection
Audit logging
Rate limiting
Secret rotation
Replay Attack Protection

Every webhook stores:

Gateway Transaction ID
Webhook ID (if provided)
Timestamp

Previously processed events are rejected.

Fraud Protection

Reject:

Amount mismatch
Unknown merchant
Invalid signature
Unknown order
Duplicate transaction
Currency mismatch

Generate security alerts.

Logging

Every payment event logs:

Payment ID

Order ID

Gateway

Amount

Status

Timestamp

Request ID

IP Address

Never log:

API secrets
Merchant secret
Card information
Sensitive payment payloads
Monitoring

Metrics:

Payment Success Rate
Average Verification Time
Failed Payments
Webhook Failures
Duplicate Webhooks
Refund Count
Revenue
Payment Latency
Retry Policy

Backend → Gateway

Network failures:

3 Retries

Exponential Backoff

Webhook processing:

Retry-safe because of idempotency.

Error Codes

Examples:

PAY001

Invalid Signature

PAY002

Payment Timeout

PAY003

Amount Mismatch

PAY004

Duplicate Payment

PAY005

Gateway Error

PAY006

Unknown Order

Never expose internal exceptions.

Future Payment Providers

The architecture must support:

Razorpay
Stripe
PhonePe
Cashfree
Paytm

without changing:

Print workflow
Business rules
Database schema

Only new gateway adapters should be required.

AI Agent Implementation Rules

When implementing payments:

Keep gateway logic isolated.
Never trust frontend payment results.
Verify every payment server-side.
Implement idempotency for all payment callbacks.
Use transactions for payment-to-job creation.
Log every financial event.
Keep the system provider-agnostic.
Preserve the existing frontend; integrate payment without redesigning the UI.
Definition of Done

The payment system is complete only if:

Order creation works.
Easebuzz checkout works.
Webhook verification works.
Signature validation passes.
Duplicate webhooks are ignored.
Print jobs are created only after verified payment.
Audit logs are written.
Tests cover success, failure, timeout, replay, and refund scenarios.
Metrics are exposed.
Secrets are never hardcoded.
End of Document