PrintBar
Data Lifecycle & Privacy Architecture

Version: 1.0

Vision

PrintBar is a Privacy-First Printing Platform.

The platform should retain customer information only for the minimum duration required to complete printing.

Once printing is successfully completed, all customer-identifiable information should be automatically removed according to configurable retention policies.

The default behavior is automatic deletion, not permanent storage.

Privacy Principles

PrintBar follows:

Privacy by Design
Data Minimization
Least Data Retention
Secure Deletion
Zero Trust
GDPR-ready architecture
DPDP Act (India) friendly architecture
Customer Data

Customer data includes

Uploaded File

Original File Name

Guest Session

IP Address

Device Fingerprint

Temporary Tokens

Signed URLs

Payment Session
What Should Be Deleted

Immediately after successful printing:

✅ Uploaded PDF

✅ Original filename

✅ Signed download URL

✅ Temporary download directory on Raspberry Pi

✅ Guest session

✅ Temporary authentication token

✅ Upload cache

What Should NOT Be Deleted

For auditing and accounting:

Keep

Job ID

Payment ID

Amount Paid

Pages Printed

Color/BW

Number of Copies

Printer Used

Kiosk Used

Print Timestamp

Payment Gateway Transaction ID

Audit Logs

Notice:

No document.

No customer identity.

No printable content.

Anonymous Print History

Instead of

User printed Resume.pdf

Store

Job

PF1023

12 Pages

₹36

Completed

2026-08-02 10:25 UTC

No filename.

No document.

File Lifecycle
Upload

↓

Validation

↓

Storage

↓

Payment

↓

Printing

↓

Completion

↓

Secure Delete

↓

Metadata Retained
Secure Delete Workflow

After

PRINT_COMPLETED

Backend immediately schedules

Delete Storage Object

↓

Delete Guest Session

↓

Delete Temporary Cache

↓

Delete Signed URLs

↓

Delete Pi Download

↓

Verify Deletion

↓

Log Completion
Raspberry Pi Cleanup

Immediately after

CUPS confirms print success

↓

Delete

downloads/*.pdf

Never keep PDFs.

Backend Cleanup

Delete

Supabase Storage File

Then

Database

storage_path = NULL

checksum = NULL

original_filename = NULL

Mark

deleted_at = timestamp
Metadata Retention

Retain only

Job ID

Payment

Price

Pages

Copies

Printer

Kiosk

Completion Time

This supports

analytics
accounting
dispute resolution

without storing documents.

Configurable Retention

Default

0 Minutes

Meaning

Immediately after print.

Future

Admin configurable

Immediately

30 Minutes

1 Hour

24 Hours

7 Days
Failed Print

If printing fails

↓

Keep file

Until

24 Hours

Then

Delete automatically.

Reason

Allows retry.

Payment Failed

Delete file

Immediately.

No reason to retain.

Upload Abandoned

User uploads

↓

Never pays

↓

Auto delete

30 Minutes
Storage Cleanup Worker

Runs

Every

15 Minutes

Deletes

expired uploads
failed uploads
abandoned uploads
expired sessions
expired URLs
Verification

Every deletion must be verified.

Log

Storage Deleted

↓

Database Updated

↓

Pi Cleaned

↓

Completed
Privacy Dashboard

Future Admin

Displays

Files Awaiting Cleanup

Cleanup Success %

Deleted Today

Storage Saved
Customer Message

Instead of

"Upload Complete"

Display

Your document will be permanently deleted immediately after successful printing.

PrintBar does not permanently store your files.

This becomes a marketing advantage.

AI Agent Rules

When implementing PrintBar:

Default to deleting user documents immediately after successful printing.
Never retain uploaded files longer than the configured retention period.
Remove temporary files from the Raspberry Pi after each completed or failed job.
Store only the minimum metadata required for operations, analytics, legal compliance, and financial records.
Never store printable document content after deletion.
Make cleanup jobs idempotent and auditable.
Allow administrators to configure retention policies, but ship with privacy-first defaults.
🚀 I Recommend One More Improvement

I would remove even the original filename from permanent storage.

Instead of storing:

Resume_Final_V12.pdf

Store only:

Original Filename

↓

Temporary Only

↓

Deleted after printing

Permanent database:

File ID

Page Count

File Size

SHA256 (optional, if retained only until deletion)

Print Settings

Payment

Job ID