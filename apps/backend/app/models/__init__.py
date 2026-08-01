"""
PrintBar Backend — Models Package

Imports all SQLAlchemy models to ensure they are registered with
the DeclarativeBase metadata before Alembic runs autogenerate.

All model classes must be imported here. Failure to import a model
will cause Alembic to miss that table during migration generation.
"""

from app.models.user import User
from app.models.kiosk import Kiosk
from app.models.printer import Printer
from app.models.uploaded_file import UploadedFile
from app.models.print_job import PrintJob
from app.models.payment import Payment
from app.models.payment_webhook import PaymentWebhook
from app.models.pricing_rule import PricingRule
from app.models.heartbeat_log import HeartbeatLog
from app.models.audit_log import AuditLog
from app.models.system_event import SystemEvent
from app.models.api_key import ApiKey
from app.models.refresh_token import RefreshToken

__all__ = [
    "User",
    "Kiosk",
    "Printer",
    "UploadedFile",
    "PrintJob",
    "Payment",
    "PaymentWebhook",
    "PricingRule",
    "HeartbeatLog",
    "AuditLog",
    "SystemEvent",
    "ApiKey",
    "RefreshToken",
]
