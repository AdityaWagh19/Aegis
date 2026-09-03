# models/db.py
import os
import uuid
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, JSON,
    BigInteger, ForeignKey, Numeric, create_engine, event, text, select
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from datetime import datetime, timezone


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./aegis.db")


class Base(DeclarativeBase):
    pass


class TenantORM(Base):
    __tablename__ = "tenants"
    tenant_id = Column(String, primary_key=True, default=lambda: f"t_{uuid.uuid4().hex[:12]}")
    name = Column(String(200), nullable=False, unique=True)
    api_key_hash = Column(String(64), nullable=False, unique=True)   # SHA-256 of raw key
    webhook_url = Column(String(500))              # Where Aegis sends decision callbacks
    callback_secret = Column(String(500))          # Encrypted; used to sign outbound callbacks
    razorpay_key_id_enc = Column(String(500))      # Fernet-encrypted Razorpay key_id
    razorpay_key_secret_enc = Column(String(500))  # Fernet-encrypted Razorpay key_secret
    razorpay_webhook_secret_enc = Column(String(500))  # Fernet-encrypted; MUST be stored to verify HMAC
    razorpay_webhook_secret_hash = Column(String(64))   # SHA-256 of plaintext secret (for fast lookup)
    # NOTE: Both _enc and _hash are stored. _hash enables fast constant-time tenant lookup
    # during webhook ingestion (without decrypting every row). _enc is decrypted once the
    # correct tenant row is identified, for actual HMAC verification.
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class TenantComplianceConfigORM(Base):
    __tablename__ = "tenant_compliance_configs"
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), primary_key=True)
    afa_threshold_general = Column(Integer, nullable=False, default=15000)
    afa_threshold_sip_insurance = Column(Integer, nullable=False, default=100000)
    max_retry_upi_autopay = Column(Integer, nullable=False, default=3)
    max_retry_enach = Column(Integer, nullable=False, default=2)
    pre_debit_notice_window_hours = Column(Integer, nullable=False, default=24)
    tier2_budget_per_minute = Column(Integer, nullable=False, default=10)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class BatchJobORM(Base):
    __tablename__ = "batch_jobs"
    job_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.tenant_id"), nullable=False)
    status = Column(String(20), nullable=False, default="queued")  # queued|processing|complete|failed
    source = Column(String(20), nullable=False, default="csv_upload")  # csv_upload|webhook
    enqueued_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    record_count = Column(Integer)
    result_payload = Column(JSON)    # BatchResult.model_dump() — replaces in-memory cache
    error = Column(Text)


class MandateEventORM(Base):
    __tablename__ = "mandate_events"
    mandate_id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    customer_id = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    mandate_type = Column(String(20), nullable=False)
    product_category = Column(String(20))
    decline_code = Column(String(50), nullable=False)
    days_since_salary_credit = Column(Integer, nullable=False)
    prior_bounce_count = Column(Integer, nullable=False, default=0)
    is_revocable = Column(Boolean, nullable=False, default=True)
    attempt_number = Column(Integer, nullable=False, default=1)
    event_timestamp = Column(DateTime(timezone=True), nullable=False)
    batch_id = Column(String, nullable=False)
    is_held_out = Column(Boolean, nullable=False, default=False)
    correct_action = Column(String(50))

    decisions = relationship("RecoveryDecisionORM", back_populates="mandate")


class RecoveryDecisionORM(Base):
    __tablename__ = "recovery_decisions"
    decision_id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    mandate_id = Column(String, ForeignKey("mandate_events.mandate_id"), nullable=False)
    tier_that_decided = Column(Integer, nullable=False)
    proposed_action = Column(String(50), nullable=False)
    compliance_approved = Column(Boolean, nullable=False)
    violation_blocked = Column(Boolean, nullable=False, default=False)
    violation_rule = Column(String(100))
    final_action = Column(String(50), nullable=False)
    outcome = Column(String(20), nullable=False)
    rationale = Column(Text)
    confidence = Column(Numeric(3, 2))
    hinglish_message = Column(Text)
    alternatives = Column(JSON)
    razorpay_response = Column(JSON)
    decided_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    mandate = relationship("MandateEventORM", back_populates="decisions")


class AuditLogORM(Base):
    __tablename__ = "audit_log"
    # BigInteger PKs are not rowid aliases on SQLite; Integer variant keeps
    # autoincrement working on SQLite while staying BigInteger on PostgreSQL.
    entry_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    tenant_id = Column(String, nullable=False, default="default")
    mandate_id = Column(String, nullable=False)
    decision_id = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    payload = Column(JSON, nullable=False)


class HumanReviewQueueORM(Base):
    __tablename__ = "human_review_queue"
    review_id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, default="default")
    mandate_id = Column(String, ForeignKey("mandate_events.mandate_id"), nullable=False)
    reason = Column(String(200), nullable=False)
    compliance_rule = Column(String(100))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True))
    resolved_by = Column(String(100))


engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Phase 9 migration: add tenant_id to existing tables (create_all only
        # creates new tables, it does not alter existing ones).
        for table in ("mandate_events", "recovery_decisions", "audit_log", "human_review_queue"):
            try:
                await conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS tenant_id VARCHAR DEFAULT 'default'")
                )
            except Exception:
                pass  # Column already exists or SQLite (which ignores IF NOT EXISTS on some versions)
        # Set NOT NULL after adding the column (PostgreSQL requires separate step)
        try:
            for table in ("mandate_events", "recovery_decisions", "audit_log", "human_review_queue"):
                await conn.execute(
                    text(f"UPDATE {table} SET tenant_id = 'default' WHERE tenant_id IS NULL")
                )
        except Exception:
            pass

        # Seed default tenant if not exists so authenticated API calls succeed out of the box
        try:
            from models.tenant import hash_api_key
            default_api_key = os.getenv("AEGIS_DEFAULT_API_KEY", "aegis_demo_key_2026")
            key_hash = hash_api_key(default_api_key)

            # Check if tenant_id = 'default' exists
            res = await conn.execute(text("SELECT tenant_id FROM tenants WHERE tenant_id = 'default'"))
            row = res.first()
            if not row:
                # Remove stale rows that might have the name 'Default Organization'
                await conn.execute(text("DELETE FROM tenants WHERE name = 'Default Organization'"))
                await conn.execute(
                    text(
                        "INSERT INTO tenants (tenant_id, name, api_key_hash, is_active, created_at) "
                        "VALUES ('default', 'Default Organization', :key_hash, true, CURRENT_TIMESTAMP)"
                    ),
                    {"key_hash": key_hash},
                )
            else:
                # Keep API key hash updated for demo/prod consistency
                await conn.execute(
                    text("UPDATE tenants SET api_key_hash = :key_hash, is_active = true WHERE tenant_id = 'default'"),
                    {"key_hash": key_hash},
                )

            # Ensure compliance config exists
            cfg_res = await conn.execute(text("SELECT tenant_id FROM tenant_compliance_configs WHERE tenant_id = 'default'"))
            if not cfg_res.first():
                await conn.execute(
                    text(
                        "INSERT INTO tenant_compliance_configs "
                        "(tenant_id, afa_threshold_general, afa_threshold_sip_insurance, max_retry_upi_autopay, max_retry_enach, pre_debit_notice_window_hours, tier2_budget_per_minute, updated_at) "
                        "VALUES ('default', 15000, 100000, 3, 2, 24, 10, CURRENT_TIMESTAMP)"
                    )
                )
        except Exception as e:
            logger.warning("Error ensuring default tenant in init_db: %s", e)



