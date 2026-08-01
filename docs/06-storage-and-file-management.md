PrintBar
Storage & File Management Specification

Version: 1.0

Status: Engineering Blueprint

Purpose

This document defines the complete document lifecycle for PrintBar.

It covers:

Upload architecture
File validation
Secure storage
Signed URLs
Download authorization
Raspberry Pi access
Cleanup
Integrity verification
Future malware scanning
Storage security

The storage layer must never expose uploaded documents publicly.

Storage Technology
Component	Technology
Object Storage	Supabase Storage
Database	PostgreSQL
Integrity	SHA-256
File URLs	Signed URLs
Validation	Backend Only
Design Principles

The storage layer shall satisfy:

Zero public buckets
Immutable uploads
Secure downloads
Temporary access
Integrity verification
Automatic cleanup
Malware-ready architecture
Audit logging
Storage Buckets

Create the following buckets.

print-files

receipts

reports

system-assets
print-files

Purpose

Stores uploaded PDFs.

Properties

Private

Encrypted

Signed URLs only

Never expose directly.

receipts

Stores generated payment receipts.

Private.

reports

Stores generated admin reports.

Private.

system-assets

Static assets.

Future use.

Bucket Rules

Every bucket must enforce:

Private access
HTTPS only
Signed URLs
Server-side authorization
No anonymous access
Supported File Types

Initially

PDF

Future

DOC

DOCX

JPG

PNG

Conversion to PDF occurs before printing.

Maximum File Size

Current Production Limit

25 MB

Reject larger uploads immediately.

Reason

Faster uploads
Better Raspberry Pi performance
Reduced storage abuse
Upload Flow
Browser

↓

Upload Request

↓

Backend Validation

↓

SHA256 Calculation

↓

PDF Validation

↓

Malware Hooks

↓

Supabase Storage

↓

Metadata Database

↓

Success Response

Frontend never uploads directly to storage.

All uploads pass through the backend.

File Naming Strategy

Never preserve user filenames.

Generate random UUID names.

Example

b70d55cf-4ab2.pdf

Original filename stored only in database.

Storage Path

Example

print-files/

2026/

08/

01/

uuid.pdf

Benefits

Better organization
Easier cleanup
Scalable storage
Metadata

Database stores

Storage Path

Original Filename

SHA256

Page Count

Upload Time

Owner

File Size

MIME Type

Expiration

Validation Result

Never trust frontend metadata.

Upload Validation

Every upload passes through:

Step 1

Extension validation.

Allowed

.pdf

Reject everything else.

Step 2

MIME validation.

Reject spoofed files.

Never trust browser MIME.

Step 3

Magic byte validation.

Confirm actual PDF signature.

Step 4

File size validation.

Maximum

25 MB
Step 5

Page count extraction.

Reject

Zero pages
Corrupted files
Step 6

Password protection detection.

Reject encrypted PDFs.

Reason

Cannot print automatically.

Step 7

Embedded JavaScript detection.

Reject.

Step 8

Embedded file detection.

Reject.

Step 9

Malformed PDF detection.

Reject corrupted structure.

Step 10

SHA-256 checksum generation.

Store checksum.

SHA-256

Every uploaded document receives

SHA256

Benefits

Integrity
Duplicate detection
Tamper detection
Duplicate Files

Same checksum

↓

Do NOT duplicate storage.

Instead

Reuse existing file metadata where appropriate while maintaining separate print job records.

Malware Architecture

Current

Validation hooks.

Future

Integrate

ClamAV

VirusTotal

Cloud scanners

Architecture should allow scanning before storage is finalized.

Signed URLs

Never expose permanent URLs.

Backend generates

Signed URL

↓

Expires

↓

Download

Expiration

5 minutes
Raspberry Pi Download Flow
Print Job

↓

Backend

↓

Generate Signed URL

↓

Send URL

↓

Pi Downloads

↓

URL Expires

Pi never accesses Supabase using service keys.

Download Authorization

Only backend may generate download links.

Rules

Payment successful
Assigned kiosk
Job active
URL not expired
File Lifecycle
Upload

↓

Validation

↓

Storage

↓

Payment

↓

Print

↓

Retention

↓

Deletion
File Retention

Completed jobs

↓

30 days

↓

Automatic deletion

Metadata remains.

File removed.

Cleanup Service

Daily worker.

Deletes

Expired files.

Expired signed URLs.

Temporary uploads.

Failed uploads.

Orphaned objects.

Failed Upload Recovery

If upload fails

↓

Delete partial object.

Rollback database transaction.

Log error.

File Integrity Verification

Before printing

Backend verifies

SHA256

Pi verifies checksum after download.

Reject mismatch.

Compression

Never recompress PDFs.

Preserve original quality.

Versioning

Files are immutable.

Never overwrite.

Every upload creates a new object.

Audit Logging

Log

Upload

Validation

Deletion

Download

Print

Cleanup

Failures

Every event includes

User

IP

Timestamp

Job

Checksum
Storage Quotas

Per upload

25 MB

Future

Per kiosk

Per organization

Per institution

Caching

Signed URLs

No browser caching.

System assets

Long cache.

Documents

Private only.

Error Responses

Examples

{
  "success": false,
  "message": "Unsupported file type."
}

Never expose internal storage paths.

Monitoring

Metrics

Upload success

Upload failures

Average upload size

Average validation time

Storage usage

Expired files

Cleanup duration

Security Requirements

Mandatory

HTTPS only
Private buckets
Signed URLs
UUID filenames
SHA256
Magic byte validation
MIME validation
Input validation
Expiring downloads
Audit logging

Never expose storage credentials.

Never expose bucket names to frontend logic beyond configuration managed by the backend.

AI Agent Rules

When implementing storage:

Never allow direct browser uploads to private storage.
Validate every file on the backend.
Generate signed URLs only after authorization.
Use UUID filenames.
Store metadata separately.
Keep uploads immutable.
Automatically clean expired objects.
Design validation as a modular pipeline so new checks (virus scanning, OCR, AI inspection) can be added without changing the upload flow.
Ensure every storage operation is logged and transactional where applicable.
Future Enhancements

The storage architecture should support:

DOC/DOCX → PDF conversion
Image → PDF conversion
OCR processing
AI document classification
Virus scanning
Watermarking
Compression analytics
Multi-region object storage
Lifecycle policies
Encrypted archives

without redesigning the storage subsystem.

End of Document

This specification defines the complete document management lifecycle for PrintBar and ensures uploaded files remain secure, traceable, and production-ready.