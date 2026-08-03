"""Initial PrintBar schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-08-01

Creates all 13 production tables for the PrintBar platform.
All tables use UUID v4 primary keys and UTC timestamps.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ─── ENUMs — PL/pgSQL blocks handle 'already exists' gracefully ──────────
    # CREATE TYPE does not support IF NOT EXISTS in PostgreSQL < 16 for ENUMs.
    # We catch duplicate_object to make migrations idempotent.
    _create_enum_safe = (
        "DO $$ BEGIN "
        "CREATE TYPE {name} AS ENUM ({values}); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$;"
    )

    op.execute(_create_enum_safe.format(
        name="user_role_enum", values="'ADMIN', 'SUPER_ADMIN'"
    ))
    op.execute(_create_enum_safe.format(
        name="kiosk_status_enum",
        values="'ONLINE', 'OFFLINE', 'PRINTING', 'MAINTENANCE', 'ERROR'"
    ))
    op.execute(_create_enum_safe.format(
        name="printer_status_enum",
        values="'READY', 'PRINTING', 'OFFLINE', 'PAPER_JAM', 'OUT_OF_PAPER', 'OUT_OF_TONER'"
    ))
    op.execute(_create_enum_safe.format(
        name="print_job_status_enum",
        values=(
            "'UPLOADED', 'VALIDATED', 'PAYMENT_PENDING', 'PAYMENT_SUCCESS', "
            "'QUEUED', 'ASSIGNED', 'DOWNLOADING', 'READY_TO_PRINT', "
            "'PRINTING', 'COMPLETED', 'FAILED', 'CANCELLED', "
            "'PAYMENT_FAILED', 'DOWNLOAD_FAILED'"
        )
    ))
    op.execute(_create_enum_safe.format(
        name="payment_status_enum",
        values="'CREATED', 'PENDING', 'PROCESSING', 'SUCCESS', 'FAILED', 'EXPIRED', 'REFUNDED'"
    ))
    op.execute(_create_enum_safe.format(name="color_mode_enum", values="'BW', 'COLOR'"))
    op.execute(_create_enum_safe.format(
        name="paper_size_enum", values="'A4', 'A3', 'LETTER', 'LEGAL'"
    ))
    op.execute(_create_enum_safe.format(
        name="system_event_severity_enum",
        values="'INFO', 'WARNING', 'ERROR', 'CRITICAL'"
    ))

    # ─── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("role", postgresql.ENUM("ADMIN", "SUPER_ADMIN", name="user_role_enum", create_type=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login_at", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"])

    # ─── kiosks ───────────────────────────────────────────────────────────────
    op.create_table(
        "kiosks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("location", sa.String(512), nullable=False),
        sa.Column("city", sa.String(100), nullable=False, server_default=""),
        sa.Column("api_key_hash", sa.String(128), nullable=False),
        sa.Column("status", postgresql.ENUM("ONLINE", "OFFLINE", "PRINTING", "MAINTENANCE", "ERROR", name="kiosk_status_enum", create_type=False), nullable=False, server_default="OFFLINE"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("ws_connected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("app_version", sa.String(32), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("last_heartbeat", sa.String(50), nullable=True),
        sa.Column("cpu_percent", sa.Float(), nullable=True),
        sa.Column("ram_percent", sa.Float(), nullable=True),
        sa.Column("disk_percent", sa.Float(), nullable=True),
        sa.Column("temperature_c", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("api_key_hash"),
    )
    op.create_index("ix_kiosks_id", "kiosks", ["id"])
    op.create_index("ix_kiosks_status", "kiosks", ["status"])

    # ─── printers ─────────────────────────────────────────────────────────────
    op.create_table(
        "printers",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kiosk_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kiosks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cups_name", sa.String(255), nullable=False),
        sa.Column("manufacturer", sa.String(100), nullable=False, server_default=""),
        sa.Column("model", sa.String(100), nullable=False, server_default=""),
        sa.Column("status", postgresql.ENUM("READY", "PRINTING", "OFFLINE", "PAPER_JAM", "OUT_OF_PAPER", "OUT_OF_TONER", name="printer_status_enum", create_type=False), nullable=False, server_default="OFFLINE"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_color", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_duplex", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("paper_level", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("toner_level", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("jobs_printed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_error_at", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_printers_id", "printers", ["id"])
    op.create_index("ix_printers_kiosk_id", "printers", ["kiosk_id"])
    op.create_index("ix_printers_status", "printers", ["status"])

    # ─── uploaded_files ───────────────────────────────────────────────────────
    op.create_table(
        "uploaded_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=True),
        sa.Column("storage_bucket", sa.String(128), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=True),
        sa.Column("mime_type", sa.String(128), nullable=False, server_default="application/pdf"),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("sha256_checksum", sa.String(64), nullable=True),
        sa.Column("is_validated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("validation_errors", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.String(50), nullable=True),
        sa.Column("expires_at", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_uploaded_files_id", "uploaded_files", ["id"])
    op.create_index("ix_uploaded_files_session_id", "uploaded_files", ["session_id"])
    op.create_index("ix_uploaded_files_is_deleted", "uploaded_files", ["is_deleted"])
    op.create_index("ix_uploaded_files_expires_at", "uploaded_files", ["expires_at"])

    # ─── print_jobs ───────────────────────────────────────────────────────────
    op.create_table(
        "print_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("uploaded_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("uploaded_files.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kiosk_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kiosks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("printer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("printers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", postgresql.ENUM("UPLOADED", "VALIDATED", "PAYMENT_PENDING", "PAYMENT_SUCCESS", "QUEUED", "ASSIGNED", "DOWNLOADING", "READY_TO_PRINT", "PRINTING", "COMPLETED", "FAILED", "CANCELLED", "PAYMENT_FAILED", "DOWNLOAD_FAILED", name="print_job_status_enum", create_type=False), nullable=False, server_default="UPLOADED"),
        sa.Column("color_mode", postgresql.ENUM("BW", "COLOR", name="color_mode_enum", create_type=False), nullable=False, server_default="BW"),
        sa.Column("paper_size", postgresql.ENUM("A4", "A3", "LETTER", "LEGAL", name="paper_size_enum", create_type=False), nullable=False, server_default="A4"),
        sa.Column("copies", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("duplex", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pages_selected", sa.Integer(), nullable=False),
        sa.Column("pages_per_sheet", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("page_range", sa.String(1024), nullable=True),
        sa.Column("orientation", sa.String(16), nullable=False, server_default="portrait"),
        sa.Column("subtotal_inr", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("gst_inr", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("total_inr", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("started_at", sa.String(50), nullable=True),
        sa.Column("completed_at", sa.String(50), nullable=True),
        sa.Column("failed_at", sa.String(50), nullable=True),
        sa.Column("failure_reason", sa.String(255), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_print_jobs_id", "print_jobs", ["id"])
    op.create_index("ix_print_jobs_session_id", "print_jobs", ["session_id"])
    op.create_index("ix_print_jobs_uploaded_file_id", "print_jobs", ["uploaded_file_id"])
    op.create_index("ix_print_jobs_kiosk_id", "print_jobs", ["kiosk_id"])
    op.create_index("ix_print_jobs_status", "print_jobs", ["status"])
    op.create_index("ix_print_jobs_idempotency_key", "print_jobs", ["idempotency_key"])

    # ─── payments ─────────────────────────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("print_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("print_jobs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("gateway", sa.String(64), nullable=False, server_default="EASEBUZZ"),
        sa.Column("gateway_order_id", sa.String(256), nullable=True),
        sa.Column("gateway_txn_id", sa.String(256), nullable=True),
        sa.Column("status", postgresql.ENUM("CREATED", "PENDING", "PROCESSING", "SUCCESS", "FAILED", "EXPIRED", "REFUNDED", name="payment_status_enum", create_type=False), nullable=False, server_default="CREATED"),
        sa.Column("amount_inr", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("payment_mode", sa.String(64), nullable=True),
        sa.Column("vpa", sa.String(255), nullable=True),
        sa.Column("bank_ref", sa.String(256), nullable=True),
        sa.Column("is_refunded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("refunded_at", sa.String(50), nullable=True),
        sa.Column("refund_amount_inr", sa.Numeric(10, 2), nullable=True),
        sa.Column("refund_txn_id", sa.String(256), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.String(50), nullable=True),
        sa.Column("paid_at", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("print_job_id"),
        sa.UniqueConstraint("gateway_order_id"),
        sa.UniqueConstraint("gateway_txn_id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_payments_id", "payments", ["id"])
    op.create_index("ix_payments_print_job_id", "payments", ["print_job_id"])
    op.create_index("ix_payments_gateway_order_id", "payments", ["gateway_order_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_index("ix_payments_expires_at", "payments", ["expires_at"])

    # ─── payment_webhooks ─────────────────────────────────────────────────────
    op.create_table(
        "payment_webhooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("gateway_txn_id", sa.String(256), nullable=True),
        sa.Column("event_type", sa.String(128), nullable=False, server_default=""),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("signature_valid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("processed_at", sa.String(50), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("amount_inr", sa.Numeric(10, 2), nullable=True),
        sa.Column("status", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gateway_txn_id"),
    )
    op.create_index("ix_payment_webhooks_id", "payment_webhooks", ["id"])
    op.create_index("ix_payment_webhooks_payment_id", "payment_webhooks", ["payment_id"])
    op.create_index("ix_payment_webhooks_gateway_txn_id", "payment_webhooks", ["gateway_txn_id"])

    # ─── pricing_rules ────────────────────────────────────────────────────────
    op.create_table(
        "pricing_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("bw_price_inr", sa.Numeric(8, 2), nullable=False),
        sa.Column("color_price_inr", sa.Numeric(8, 2), nullable=False),
        sa.Column("a3_multiplier", sa.Numeric(4, 2), nullable=False, server_default="1.75"),
        sa.Column("legal_multiplier", sa.Numeric(4, 2), nullable=False, server_default="1.25"),
        sa.Column("duplex_discount", sa.Numeric(4, 2), nullable=False, server_default="0.00"),
        sa.Column("gst_percent", sa.Numeric(5, 2), nullable=False, server_default="18.00"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("valid_from", sa.String(50), nullable=False),
        sa.Column("valid_until", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pricing_rules_id", "pricing_rules", ["id"])
    op.create_index("ix_pricing_rules_is_active", "pricing_rules", ["is_active"])

    # ─── heartbeat_logs ───────────────────────────────────────────────────────
    op.create_table(
        "heartbeat_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kiosk_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kiosks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("app_version", sa.String(32), nullable=True),
        sa.Column("cpu_percent", sa.Float(), nullable=True),
        sa.Column("ram_percent", sa.Float(), nullable=True),
        sa.Column("disk_percent", sa.Float(), nullable=True),
        sa.Column("temperature_c", sa.Float(), nullable=True),
        sa.Column("printer_status", sa.String(64), nullable=True),
        sa.Column("active_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("network_latency_ms", sa.Float(), nullable=True),
        sa.Column("extra", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_heartbeat_logs_id", "heartbeat_logs", ["id"])
    op.create_index("ix_heartbeat_logs_kiosk_id", "heartbeat_logs", ["kiosk_id"])

    # ─── audit_logs ───────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_kiosk_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kiosks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_type", sa.String(16), nullable=False, server_default="SYSTEM"),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("entity_id", sa.String(128), nullable=True),
        sa.Column("print_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("print_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("result", sa.String(16), nullable=False, server_default="SUCCESS"),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_id", "audit_logs", ["id"])
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_actor_kiosk_id", "audit_logs", ["actor_kiosk_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_print_job_id", "audit_logs", ["print_job_id"])

    # ─── system_events ────────────────────────────────────────────────────────
    op.create_table(
        "system_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("severity", postgresql.ENUM("INFO", "WARNING", "ERROR", "CRITICAL", name="system_event_severity_enum", create_type=False), nullable=False, server_default="INFO"),
        sa.Column("source", sa.String(128), nullable=False, server_default="backend"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("resolved_at", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_events_id", "system_events", ["id"])
    op.create_index("ix_system_events_event_type", "system_events", ["event_type"])
    op.create_index("ix_system_events_severity", "system_events", ["severity"])
    op.create_index("ix_system_events_resolved", "system_events", ["resolved"])

    # ─── api_keys ─────────────────────────────────────────────────────────────
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kiosk_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kiosks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("last_used_at", sa.String(50), nullable=True),
        sa.Column("revoked_at", sa.String(50), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("ix_api_keys_id", "api_keys", ["id"])
    op.create_index("ix_api_keys_kiosk_id", "api_keys", ["kiosk_id"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])
    op.create_index("ix_api_keys_is_active", "api_keys", ["is_active"])

    # ─── refresh_tokens ───────────────────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.String(50), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("revoked_at", sa.String(50), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("last_used_at", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_refresh_tokens_id", "refresh_tokens", ["id"])
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])
    op.create_index("ix_refresh_tokens_is_revoked", "refresh_tokens", ["is_revoked"])


def downgrade() -> None:
    op.drop_table("refresh_tokens")
    op.drop_table("api_keys")
    op.drop_table("system_events")
    op.drop_table("audit_logs")
    op.drop_table("heartbeat_logs")
    op.drop_table("pricing_rules")
    op.drop_table("payment_webhooks")
    op.drop_table("payments")
    op.drop_table("print_jobs")
    op.drop_table("uploaded_files")
    op.drop_table("printers")
    op.drop_table("kiosks")
    op.drop_table("users")

    for enum_name in [
        "user_role_enum", "kiosk_status_enum", "printer_status_enum",
        "print_job_status_enum", "payment_status_enum",
        "color_mode_enum", "paper_size_enum", "system_event_severity_enum",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
