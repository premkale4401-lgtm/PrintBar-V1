PrintBar
Raspberry Pi Edge Platform Specification

Version: 1.0

Status: Engineering Blueprint

Purpose

This document defines the complete Raspberry Pi Edge Platform.

The Raspberry Pi is NOT a backend server.

It is NOT a payment processor.

It is NOT a database.

It is an Edge Device responsible for securely executing print jobs assigned by the backend.

Philosophy

The Raspberry Pi should be completely stateless.

If the SD card dies tomorrow,

A new Raspberry Pi should be able to:

Flash OS
Register
Authenticate
Sync
Resume operation

within minutes.

No customer information should permanently exist on the Raspberry Pi.

Edge Architecture
                  Cloud

                    │

             FastAPI Backend

                    │

          Secure WebSocket (TLS)

                    │

         Raspberry Pi Edge Device

        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼

   Job Manager   Printer   Heartbeat

        │

        ▼

    Brother Printer
Responsibilities

The Raspberry Pi SHALL:

Register itself
Authenticate
Maintain WebSocket connection
Send heartbeat
Receive jobs
Download PDFs
Verify SHA256
Print using CUPS
Report progress
Report printer health
Retry failed downloads
Auto reconnect
Auto start on boot
Rotate logs

The Raspberry Pi SHALL NEVER:

Store customer data permanently
Verify payments
Calculate prices
Generate signed URLs
Make business decisions
Access the database
Communicate directly with Supabase
Software Stack

Operating System

Raspberry Pi OS Lite 64-bit

Programming Language

Python 3.12+

Printing

CUPS

Communication

WebSocket

Process Management

systemd

Logging

Python Logging

Configuration

YAML
Folder Structure
kiosk/

app/

client/

jobs/

printer/

downloads/

config/

heartbeat/

auth/

websocket/

monitoring/

logs/

utils/

systemd/

tests/
Configuration

Example

device:
  kiosk_id:
  api_url:
  websocket_url:

printer:
  default:
  timeout:

heartbeat:
  interval: 30

logging:
  level: INFO

downloads:
  folder:

Secrets must never be stored inside Git.

Boot Sequence
Power On

↓

systemd

↓

Kiosk Service

↓

Load Config

↓

Authenticate

↓

Register

↓

WebSocket

↓

Heartbeat

↓

Ready
Device Registration

First boot only.

Backend issues

Kiosk ID

API Key

Stored securely.

Future

Support TPM/HSM.

Authentication

Every request includes

Kiosk ID

API Key

Timestamp

Backend verifies.

JWT session created.

Heartbeat

Every

30 Seconds

Payload

{
  "kioskId":"",
  "printerStatus":"",
  "cpu":"",
  "memory":"",
  "disk":"",
  "temperature":"",
  "uptime":"",
  "timestamp":""
}

Missing

3 heartbeats

↓

Device Offline

WebSocket

Single persistent connection.

Reconnect automatically.

Uses

Exponential Backoff.

Supported Messages

REGISTER

PING

PONG

NEW_JOB

DOWNLOAD

PRINT

CANCEL

STATUS

ERROR
Job Processing

Workflow

Receive Job

↓

Validate

↓

Download

↓

SHA256

↓

Print

↓

Progress

↓

Complete
Download

Backend sends

Signed URL

↓

Download

↓

Verify checksum

↓

Delete URL

Temporary Files

Stored

downloads/

Automatically deleted

After

Successful printing

or

Failure recovery.

Printing

Backend sends

{
  "jobId":"",
  "copies":2,
  "color":"BW"
}

Printer Layer

↓

CUPS

↓

Brother Printer

Printer Abstraction

Never call CUPS directly from business logic.

Instead

Printer Interface

↓

CUPS Adapter

Future

HP Adapter

Canon Adapter

Network Printer Adapter

Print Queue

Maximum

10 Jobs

Future

Dynamic queue.

Retry Rules

Download

3 Attempts

Heartbeat

Infinite

WebSocket

Infinite

Print

Manual review

Error Types
Printer Offline

Paper Jam

Out Of Paper

Out Of Toner

USB Disconnect

Download Failed

Checksum Failed

Timeout

Every error reported immediately.

Health Monitoring

Monitor

CPU

RAM

Temperature

Disk

Printer

WebSocket

Heartbeat

Uptime

Critical temperature

80°C

Warning

70°C
Logging

Log

Startup

Authentication

Heartbeat

Downloads

Printing

Errors

Shutdown

Rotation

10 MB

10 Files
systemd

Service

printbar-kiosk.service

Features

Auto Restart

Restart Delay

Boot Startup

Health Monitoring

Example

Restart=always

RestartSec=5
Offline Behaviour

If backend unavailable

↓

Continue heartbeat attempts

↓

Reject new jobs

↓

Recover automatically

If printer unavailable

↓

Report status

↓

Keep WebSocket alive

↓

Await recovery

OTA Updates

Future

Backend

↓

Version Check

↓

Download

↓

Verify Signature

↓

Install

↓

Restart Service

Never auto-update

Without verification.

Security
TLS only
API Key authentication
Signed downloads
SHA256 verification
No plaintext secrets
Minimal permissions
Read-only configuration where possible
Firewall enabled
Diagnostics

Admin should remotely view

Version
Uptime
CPU
RAM
Disk
Printer State
Queue
Logs
Last Heartbeat

without SSH access.

Fleet Management

Future support

1000+

Devices

Features

Group devices
Region
Tags
Online Status
Firmware Version
Restart Device
Maintenance Mode
Raspberry Pi State Machine
BOOT

↓

REGISTERING

↓

AUTHENTICATING

↓

READY

↓

DOWNLOADING

↓

PRINTING

↓

READY

Failure

ERROR

↓

RECOVERY

↓

READY
Monitoring Metrics

Expose

CPU %

Memory %

Disk %

Temperature

Printer Status

Jobs Printed

Average Print Time

Download Time

Heartbeat Latency

Reconnect Count
Disaster Recovery

If SD card fails

↓

Flash new OS

↓

Register device

↓

Restore configuration

↓

Resume service

No customer documents should need recovery from the device.

AI Agent Rules

When implementing the Raspberry Pi platform:

Keep the Pi stateless.
Encapsulate printer interactions behind an abstraction layer.
Use systemd for service management.
Ensure automatic reconnection for WebSocket communication.
Verify file integrity before printing.
Remove temporary files after job completion.
Design for unattended 24/7 operation.
Never embed backend business logic in the kiosk client.
Keep the implementation modular so additional printer types or transport protocols can be added without changing the core job manager.
Definition of Done

The Raspberry Pi platform is complete only if:

Boots automatically into the kiosk service.
Authenticates securely.
Maintains a stable WebSocket connection.
Receives print jobs.
Downloads and verifies files.
Prints successfully via CUPS.
Reports real-time status and health.
Recovers automatically from network interruptions.
Cleans temporary files.
Produces structured logs.
Can be remotely monitored.
End of Document