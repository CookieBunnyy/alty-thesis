"""Agent recruitment and periodic agent assessments (ALTY only)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Applicant pipeline, in order. REJECTED and WITHDRAWN close an application.
APPLICANT_STAGES = ("APPLIED", "SCREENING", "INTERVIEW", "APPROVED", "ONBOARDED")
APPLICANT_CLOSED = ("REJECTED", "WITHDRAWN")
APPLICANT_STATUSES = APPLICANT_STAGES + APPLICANT_CLOSED
APPLICANT_SOURCES = ("REFERRAL", "WALK_IN", "ONLINE", "JOB_FAIR", "SOCIAL_MEDIA", "OTHER")

# Assessment criteria, each scored 1-5.
ASSESSMENT_CRITERIA = ("sales_performance", "client_satisfaction", "documentation_compliance",
                       "product_knowledge", "teamwork")


class AgentApplicant(Base):
    """Someone applying to become an Abellar Realty agent."""

    __tablename__ = "agent_applicants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    branch_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    desired_designation: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    experience_years: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    has_license: Mapped[bool] = mapped_column(default=False, nullable=False)
    license_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    screening_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100
    interview_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="APPLIED", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [{"status", "at", "by", "note"}], oldest first.
    history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    agent_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("agents.agent_id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow,
                                                 onupdate=datetime.utcnow)


class AgentAssessment(Base):
    """A periodic evaluation of an agent: scored criteria plus the recorded
    figures for the period, so the score can be checked later."""

    __tablename__ = "agent_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    scores: Mapped[dict] = mapped_column(JSON, nullable=False)        # criterion -> 1..5
    overall: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    rating: Mapped[str] = mapped_column(String(40), nullable=False)
    recommendation: Mapped[str | None] = mapped_column(String(60), nullable=True)
    kpis: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # recorded figures
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
