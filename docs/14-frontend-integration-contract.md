PrintBar
Frontend Integration Contract

Version: 1.0

Status: Implementation Contract

Purpose

This document defines how the backend integrates with the existing PrintBar frontend.

This frontend has already been designed and approved.

The backend implementation must integrate into the current frontend instead of replacing it.

The frontend is considered the UI Source of Truth.

Primary Rule
DO NOT REDESIGN THE FRONTEND.

The following are strictly prohibited:

Rebuilding pages
Replacing layouts
Removing animations
Replacing components
Changing spacing
Changing typography
Changing color palette
Changing navigation
Changing responsiveness
Removing transitions
Removing 3D effects
Changing branding
Allowed Changes

Backend integration may only:

Replace mock data
Connect APIs
Connect WebSockets
Connect Easebuzz
Connect Supabase
Add Loading States
Add Error States
Add Success States
Add Validation
Add Toast Notifications
Add Skeleton Loaders
Add Retry Buttons
Improve Accessibility
Frontend Architecture

Frontend remains

Presentation Layer

Business logic moves to

FastAPI Backend
Data Flow
User

↓

Frontend UI

↓

REST API

↓

Backend

↓

Database

↓

Response

↓

Frontend Update

Never

Frontend

↓

Database
State Management

Frontend state stores only

Current Upload
Current Payment
Current Job
Current Session
UI State

Never

Business Rules
Pricing Logic
Payment Verification
Mock Data Replacement

Every hardcoded value should become API driven.

Examples

Current

price = 30

Replace with

GET /pricing/calculate

Current

status = "Printing"

Replace with

WebSocket Event
Page Mapping
Landing Page

Current

QR Landing

Backend

No API

Only

POST /session

Creates Guest Session

Upload Page

Current

Upload Component

Integrate

POST /uploads

Replace mock upload.

Upload Progress

Replace simulated progress.

Use

Actual upload progress

Axios

↓

Backend

Upload Success

Current

Hardcoded

Replace

Backend response

{
    "fileId":"",
    "pages":12
}
Upload Errors

Display backend errors.

Example

UPLOAD_001

Friendly message.

Print Options

Current

Local calculations.

Remove.

Backend

POST /pricing/calculate

Frontend only renders response.

Price Card

Current

Static.

Replace

{
    "subtotal":60,
    "gst":12,
    "total":72
}
Payment Page

Integrate

POST /payments/create

Returns

paymentUrl

Redirect user.

Payment Result

Never trust query parameters.

Instead

Poll

or

WebSocket

↓

Backend

↓

Payment Status

Printing Page

Current

Static animation.

Keep animation.

Replace progress

with

WebSocket updates.

Status Updates

Replace

Fake Progress

With

DOWNLOADING

↓

PRINTING

↓

COMPLETED

Realtime.

Completion Screen

Current

Static.

Replace

Backend

GET /jobs/{id}
WebSocket

Frontend connects

Immediately

after

Payment Success.

Events

JOB_ASSIGNED

DOWNLOADING

PRINTING

PAGE_PROGRESS

COMPLETED

FAILED
Upload Validation

Client-side

Only

Basic

File Type
File Size

Everything else

Backend.

Forms

Use

React Hook Form

Zod

Never manual validation.

Loading States

Every API

Requires

Loading UI.

No blank screens.

Skeletons

Required

For

Upload
Pricing
Payment
Status
Error Handling

Every API

Requires

Error State.

Never

Silent failures.

Retry UX

Every failure

Should provide

Retry

when applicable.

Session Management

Frontend stores

Guest Session

No login required.

Session expires

Automatically.

Authentication

Guest

JWT

Stored

Secure Cookie

Preferred.

Toast Notifications

Use

shadcn

Toast

For

Upload Success

Payment Failed

Print Completed

Network Error

WebSocket Reconnect

Automatically reconnect.

Never require

Page Refresh.

API Layer

All HTTP requests

Must go through

services/

Never call

Axios

inside components.

Example

upload.service.ts

payment.service.ts

job.service.ts

session.service.ts
React Query

Use

TanStack Query

For

Pricing
Job Status
Admin Data

Avoid manual fetch logic.

Environment Variables

Frontend

Never contains

Secrets.

Only

NEXT_PUBLIC_API_URL

etc.

Accessibility

Maintain

Keyboard Navigation

ARIA

Focus States

Screen Readers

Performance

Lazy load

Large Components.

Memoize

Heavy Components.

Optimize

Images.

Component Rules

Components

Should remain

Presentational.

Business logic

Moves to

Hooks

↓

Services

↓

Backend

Folder Rules

Never

Mix

API

and

UI.

Example

components/

services/

hooks/
AI Agent Rules

When integrating the backend:

Do not redesign the frontend.
Preserve all animations.
Preserve layout.
Preserve responsiveness.
Preserve styling.
Replace every mock API with a real backend endpoint.
Move business logic out of components.
Keep components reusable.
Use React Query for server state.
Use WebSockets for real-time job updates.
Use the existing component hierarchy.
Minimize code changes outside integration points.
Acceptance Criteria

The frontend integration is complete only if:

No visual regressions are introduced.
Existing animations continue to work.
Mock data is fully removed.
Backend APIs are fully integrated.
Easebuzz payment flow works.
Real-time job status works.
Error and loading states are implemented.
The UI remains pixel-consistent with the approved design.
End of Document