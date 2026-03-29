"""
Base agent — all five AI agents inherit from this.
Provides a standard interface, context injection, and audit logging.
"""
from __future__ import annotations
import json
import time
import logging
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.orm import Session

from app.services.nim_client import nim
from app.database.models import AgentSession, AgentType, User, FinancialProfile

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Every agent must implement `_build_prompt()` and `_pre_compute()`.
    `run()` is the public entry point.
    """

    agent_type: AgentType  # override in subclass

    # ── Public API ────────────────────────────────────────────────────────────

    def run(
        self,
        db: Session,
        user: User,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Orchestrate a full agent call:
        1. Load user's financial profile from DB
        2. Run deterministic pre-computation (pure math, no LLM)
        3. Build prompt and call NIM
        4. Parse and structure the response
        5. Persist to audit log
        6. Return structured result
        """
        t0 = time.monotonic()
        profile = self._load_profile(db, user)

        # Step 2: deterministic pre-compute
        computed = self._pre_compute(profile, payload)

        # Step 3+4: LLM enrichment
        system_prompt = self._system_prompt()
        user_message = self._build_prompt(profile, payload, computed)
        raw_response, usage = nim.complete(
            system_prompt=system_prompt,
            user_message=user_message,
            json_mode=True,
        )

        # Step 5: parse LLM JSON
        try:
            ai_result = json.loads(raw_response)
        except json.JSONDecodeError:
            logger.warning("NIM returned non-JSON; wrapping in text field")
            ai_result = {"narrative": raw_response}

        # Merge computed numbers with AI narrative
        result = {**computed, **ai_result, "agent": self.agent_type.value}

        # Step 6: audit log
        self._log_session(
            db=db,
            user=user,
            request_payload=payload,
            response=result,
            usage=usage,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

        return result

    # ── Abstract methods ──────────────────────────────────────────────────────

    @abstractmethod
    def _pre_compute(
        self,
        profile: FinancialProfile | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Return deterministically computed numbers (no LLM)."""

    @abstractmethod
    def _build_prompt(
        self,
        profile: FinancialProfile | None,
        payload: dict[str, Any],
        computed: dict[str, Any],
    ) -> str:
        """Build the user-turn message to send to NIM."""

    @abstractmethod
    def _system_prompt(self) -> str:
        """Return the system prompt for this agent."""

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _load_profile(db: Session, user: User) -> FinancialProfile | None:
        return db.query(FinancialProfile).filter(
            FinancialProfile.user_id == user.id
        ).first()

    @staticmethod
    def _fmt_inr(amount: float) -> str:
        """Format a number as Indian currency string (₹12,34,567)."""
        if amount >= 10_000_000:
            return f"₹{amount/10_000_000:.2f} Cr"
        if amount >= 100_000:
            return f"₹{amount/100_000:.2f} L"
        return f"₹{amount:,.0f}"

    def _log_session(
        self,
        db: Session,
        user: User,
        request_payload: dict,
        response: dict,
        usage: dict,
        latency_ms: int,
    ):
        try:
            session = AgentSession(
                user_id=user.id,
                agent=self.agent_type,
                request_json=json.dumps(request_payload, default=str),
                response_json=json.dumps(response, default=str),
                nim_prompt_tokens=usage.get("prompt_tokens", 0),
                nim_completion_tokens=usage.get("completion_tokens", 0),
                latency_ms=latency_ms,
            )
            db.add(session)
            db.commit()
        except Exception as e:
            logger.error("Failed to log agent session: %s", e)
            db.rollback()
