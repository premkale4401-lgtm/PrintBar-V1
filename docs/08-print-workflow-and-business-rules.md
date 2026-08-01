PrintBar
Print Workflow & Business Rules Specification

Version: 1.0

Status: Engineering Blueprint

Purpose

This document defines the complete lifecycle of a PrintBar print job.

Every backend service, frontend component, Raspberry Pi kiosk, payment service, and administrator workflow must follow this lifecycle.

No component may bypass these business rules.

Core Philosophy

A print job is a state machine.

It always exists in exactly one state.

Transitions are strictly controlled by the backend.

Neither the frontend nor the Raspberry Pi may change business state directly.

End-to-End Workflow
User

↓

Scan QR

↓

Website Opens

↓

Create Guest Session

↓

Upload File

↓

Validate File

↓

Extract Metadata

↓

Select Print Options

↓

Price Calculation

↓

Create Payment Order

↓

Easebuzz Payment

↓

Payment Verification

↓

Create Print Job

↓

Assign Kiosk

↓

Generate Signed URL

↓

Notify Raspberry Pi

↓

Download PDF

↓

Verify SHA256

↓

Print

↓

Send Progress

↓

Completed

↓

Cleanup
Workflow Principles

The backend is the only authority that may:

calculate pricing
verify payments
create print jobs
assign kiosks
authorize downloads
mark jobs completed
delete files
Workflow States
SESSION_CREATED

↓

FILE_UPLOADED

↓

FILE_VALIDATED

↓

PRINT_OPTIONS_SELECTED

↓

PRICE_CALCULATED

↓

PAYMENT_CREATED

↓

PAYMENT_PENDING

↓

PAYMENT_SUCCESS

↓

JOB_CREATED

↓

JOB_ASSIGNED

↓

DOWNLOAD_READY

↓

DOWNLOADING

↓

PRINT_READY

↓

PRINTING

↓

PRINT_COMPLETED

↓

ARCHIVED

Failure States

UPLOAD_FAILED

VALIDATION_FAILED

PAYMENT_FAILED

PAYMENT_TIMEOUT

PAYMENT_CANCELLED

DOWNLOAD_FAILED

PRINTER_OFFLINE

PAPER_JAM

OUT_OF_PAPER

PRINT_FAILED

JOB_CANCELLED

Every state transition is logged.

Step 1
QR Scan

The QR code opens

https://printbar.in

The QR never contains:

pricing
kiosk id
secrets

Only routing information.

Step 2
Guest Session

Immediately after opening

Backend creates

{
    "sessionId":"",
    "expiresAt":"",
    "status":"ACTIVE"
}

Session expiration

24 Hours
Business Rules

One session

↓

Many uploads

One upload

↓

One payment

One payment

↓

One print job

Step 3
Upload

Allowed

PDF

Current size limit

25 MB

Maximum pages

500

Reject

encrypted
corrupted
javascript
embedded files
Metadata Extraction

Backend extracts

Pages

Size

Checksum

PDF Version

Orientation

Dimensions
Step 4
Print Settings

Allowed settings

Copies

Black & White

Color

Future

Duplex

Page Range

Paper Size

Orientation

Quality
Business Rule

Frontend sends

{
    "copies":2,
    "color":"BW"
}

Backend validates.

Frontend never calculates total price.

Step 5
Pricing

Backend loads

Pricing Rules

Example

BW

₹3

Color

₹10

Example calculation

12 Pages

BW

2 Copies

↓

12 × 2 × 3

↓

₹72

Price stored permanently.

Later pricing changes do not affect existing jobs.

Step 6
Payment

Backend creates

Easebuzz Order

Returns

{
    "paymentUrl":"..."
}

Frontend redirects.

Payment Timeout

Recommended

15 Minutes

Expired

↓

Payment Failed

Payment Verification

Only webhook

may

mark payment successful.

Frontend success page is

never trusted.

Idempotency

Receiving

same webhook

10 times

↓

One payment

↓

One print job

Step 7
Print Job Creation

Only after

PAYMENT_SUCCESS

Backend creates

Print Job

↓

Status

QUEUED
Print Job Object

Contains

File

Printer Settings

Price

Payment

Assigned Kiosk

Current State
Step 8
Kiosk Assignment

Future

Multiple kiosks

Algorithm

Online

↓

Healthy

↓

Printer Ready

↓

Nearest

↓

Least Busy

Current

One kiosk

Always assigned.

Assignment Rules

Never assign

Offline kiosk.

Never assign

Printing kiosk

if queue full.

Step 9
Download Authorization

Backend generates

Signed URL

Expiration

5 Minutes

Backend sends

{
    "jobId":"",
    "downloadUrl":"",
    "checksum":""
}
Step 10
Raspberry Pi

Receives

NEW_JOB

Workflow

Receive

↓

Download

↓

SHA256

↓

CUPS

↓

Print
Verification

Pi compares

Downloaded checksum

↓

Backend checksum

Mismatch

↓

Reject

↓

Report Failure

Print Progress

Pi reports

DOWNLOADING

READY

PRINTING

PAGE_PROGRESS

COMPLETED

Backend updates database.

Frontend receives updates through WebSocket.

Printer Errors

Supported

Offline

Out of Paper

Paper Jam

Out of Toner

Door Open

Unknown Error
Retry Rules

Download

3 attempts

Heartbeat

Infinite

WebSocket

Exponential Backoff

Printing

No automatic retry

Requires admin review

Cancellation Rules

Allowed

Before payment

Allowed

During payment timeout

Not allowed

After printing begins

Refund Rules

Future

Automatic

Manual

Partial

Cleanup

After

Completed

↓

30 Days

↓

Delete PDF

↓

Keep Metadata

Logging

Every transition logged

Examples

Upload

Validation

Payment

Assignment

Download

Printing

Completion

Failure
Notifications

Frontend receives

Upload Success

Payment Pending

Payment Success

Queued

Printing

Completed

Failed

Realtime

via

WebSocket

Performance Targets

Upload

<2 sec validation

Pricing

<100 ms

Payment Creation

<500 ms

Print Dispatch

<1 sec

Status Updates

<100 ms

Business Constraints

A print job:

Cannot exist without a validated file.
Cannot print without a successful payment.
Cannot be assigned to an offline kiosk.
Cannot be completed without printer confirmation.
Cannot be modified after printing begins.
Sequence Diagram
User
 │
 │ Upload
 ▼
Backend
 │
 │ Validate
 ▼
Storage
 │
 │ Save
 ▼
Backend
 │
 │ Calculate Price
 ▼
Easebuzz
 │
 │ Pay
 ▼
Webhook
 │
 │ Verify
 ▼
Backend
 │
 │ Create Job
 ▼
Kiosk
 │
 │ Download
 │
 │ Print
 ▼
Backend
 │
 │ Update Status
 ▼
Frontend
Future Enhancements

The workflow should be designed to support:

Multiple kiosks
Multiple printers per kiosk
Print queues
Reservations
Scheduled printing
Campus wallets
Coupons
Promo codes
Bulk uploads
AI print optimization
OCR
Document preview
Duplex
Page range
Internationalization

without redesigning the workflow engine.

AI Agent Rules

When implementing the workflow:

Treat the print job as a strict state machine.
Never allow invalid state transitions.
Perform all business logic in the backend.
Make payment processing idempotent.
Log every state transition.
Ensure every transition is transactional where required.
Keep the Raspberry Pi as an execution agent only.
Preserve the existing frontend and connect it to this workflow without redesigning the UI.
End of Document