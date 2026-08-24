# models/db.py
import os
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, JSON,
    BigInteger, ForeignKey, Numeric, create_engine, event
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from datetime import datetime, timezone


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./aegis.db")


class Base(DeclarativeBase):
    pass


class MandateEventORM(Base):
    __tablename__ = "mandate_events"
    mandate_id = Column(String, primary_key=True)
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
    mandate_id = Column(String, nullable=False)
    decision_id = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    payload = Column(JSON, nullable=False)


class HumanReviewQueueORM(Base):
    __tablename__ = "human_review_queue"
    review_id = Column(String, primary_key=True)
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
