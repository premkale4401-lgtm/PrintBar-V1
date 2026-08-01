PrintBar
Admin Dashboard Specification

Version: 1.0

Status: Engineering Blueprint

Purpose

The Admin Dashboard is the operational control center of PrintBar.

It enables administrators to:

Monitor the health of the platform.
Manage Raspberry Pi kiosks.
Monitor printers.
Track print jobs.
Manage pricing.
View payments.
Monitor storage.
Review audit logs.
Diagnose failures.
Manage future franchise deployments.

The dashboard is never exposed to public users.

Design Philosophy

The dashboard should resemble enterprise SaaS platforms.

References

Stripe Dashboard
Vercel Dashboard
Cloudflare Dashboard
Linear
GitHub Enterprise

Design goals

Fast
Minimal
Information Dense
Real-time
Responsive
Keyboard Friendly
Admin Roles

Initial

SUPER_ADMIN

ADMIN

OPERATOR

Future

SUPPORT

ANALYST

FRANCHISE_OWNER
Sidebar Navigation
Dashboard

Print Jobs

Payments

Kiosks

Printers

Pricing

Storage

Analytics

Audit Logs

Users

System

Settings
Dashboard Home

Widgets

Today's Revenue

Today's Jobs

Jobs In Queue

Active Kiosks

Offline Kiosks

Printer Errors

Storage Usage

Success Rate

Average Print Time

Charts

Revenue

Jobs

Printer Health

Payments

Upload Size

Daily Usage
Dashboard Metrics

Display

Jobs Today

Jobs This Month

Revenue Today

Revenue This Month

Average Job Time

Payment Success %

Printer Availability %

Storage Used

Average Upload Size

Update

Realtime

Print Jobs Module

List

Job ID

User Session

Pages

Copies

Price

Status

Kiosk

Printer

Created

Completed

Actions

View

Retry

Cancel

Export

Filters

Status

Date

Kiosk

Payment

Printer
Job Details

Display

Timeline

Uploaded File

Pages

Print Settings

Payment

Printer

Logs

Audit History
Payment Module

Display

Payment ID

Amount

Gateway

Status

Transaction ID

Created

Paid

Actions

Refund

View

Export

Metrics

Success %

Failure %

Refunds

Revenue
Kiosk Management

Each Raspberry Pi

Card

Displays

Name

Online

Temperature

CPU

RAM

Disk

Printer

Version

Last Heartbeat

Actions

Restart Service

Maintenance Mode

Disable

Rename

View Logs

Update Firmware (Future)

Realtime

Green

↓

Healthy

Yellow

↓

Warning

Red

↓

Offline

Kiosk Detail Page

Sections

Overview

Health

Printer

Current Job

Queue

Logs

Configuration

History
Printer Module

Every printer displays

Manufacturer

Model

Status

Paper

Toner

Jobs Printed

Last Error

Actions

Test Print

Restart Queue

Pause

Resume

Printer Alerts

Paper Jam

Out of Paper

Out of Toner

Offline

USB Error
Pricing Module

Editable

BW Price

Color Price

GST

Discount

Offers

Changes

Require confirmation.

Logged.

Storage Module

Displays

Storage Used

Files

Expired Files

Cleanup Jobs

Largest Files

Actions

Cleanup

Export

Search
Audit Logs

Immutable.

Display

Time

Actor

Action

Entity

IP

Result

Filters

Date

User

Module

Action

Never editable.

Analytics

Charts

Daily Revenue

Print Volume

Top Kiosks

Peak Hours

Payment Success

Average Upload Size

Average Print Duration

Future

Predictive analytics.

Notifications

Admin receives alerts for

Offline Kiosk

Printer Error

Failed Payment

Webhook Failure

Storage Full

High Temperature

Delivery

Dashboard
Email (future)
Push (future)
Search

Global search

Supports

Job ID

Payment ID

Kiosk

Printer

Transaction ID

Target response

<300 ms

System Module

Displays

API Status

Database

Redis

Storage

Queue

WebSocket

Version

Uptime

Health indicators

Green

Yellow

Red

Settings

Manage

Pricing

Retention

Security

Feature Flags

API Keys

Branding

Maintenance Mode
Feature Flags

Examples

Enable Coupons

Enable OCR

Enable Duplex

Enable Multi Printer

Enable AI Validation

No redeployment required.

Exports

CSV

Excel

PDF

Supported for

Jobs
Payments
Analytics
Audit Logs
Keyboard Shortcuts

Examples

/

Search

G J

Jobs

G K

Kiosks

G P

Payments

?

Help overlay.

Dashboard Security

Mandatory

Admin JWT
Refresh Token Rotation
RBAC
CSRF Protection
Audit Logging
Session Timeout
Session Timeout

Idle

30 Minutes

Auto logout.

Performance Targets

Dashboard load

<2 sec

Realtime updates

<200 ms

Search

<300 ms

Charts

<1 sec

Future Modules
Fleet Management

Multi Organization

Franchise Dashboard

Support Desk

Coupons

Subscriptions

Campus Wallet

Invoices

AI Insights

Predictive Maintenance
AI Agent Rules

When implementing the Admin Dashboard:

Maintain the existing PrintBar design language.
Build a dedicated admin layout without affecting the customer-facing frontend.
Use server-side pagination for large datasets.
Use WebSockets for real-time operational updates.
Ensure every destructive action requires confirmation.
Protect all routes with RBAC.
Record every administrative action in the audit log.
Design components to support future multi-tenant and franchise deployments.
Definition of Done

The Admin Dashboard is complete only if:

Dashboard metrics update in real time.
Kiosks and printers can be monitored live.
Jobs and payments are searchable and exportable.
Pricing changes are controlled and audited.
System health is visible.
RBAC is enforced.
Performance targets are met.
All administrative actions are logged.
End of Document