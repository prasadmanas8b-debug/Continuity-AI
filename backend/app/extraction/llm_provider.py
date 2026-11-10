import hashlib

import json
import re
import uuid
from typing import Any, Dict, List, Optional, Protocol

from pydantic import BaseModel, Extra, Field

from app.core.config import settings
from app.core.errors import ContinuityException
from app.schemas.enums import ErrorCode, FactType, SupportStatus


class SourceChunk(BaseModel):
    source_id: str
    text: str
    char_offset: int
    filename: Optional[str] = None


class QuoteItem(BaseModel):
    source_id: str
    exact_quote: str


class ExtractedClaimItem(BaseModel):
    item_id: str = Field(..., pattern=r"^[a-z0-9_]{3,60}$")
    fact_type: FactType
    statement: str = Field(..., min_length=1, max_length=1000)
    owner: Optional[str] = None
    quotes: List[QuoteItem] = []
    audience_roles: List[str] = []

    class Config:
        extra = Extra.forbid


class ExtractionOutput(BaseModel):
    claims: List[ExtractedClaimItem] = []

    class Config:
        extra = Extra.forbid


class SupportAssessment(BaseModel):
    support_status: SupportStatus
    note: Optional[str] = None


class Relation(BaseModel):
    relation: str  # consistent | contradiction | explicit_supersession | unclear
    summary: str
    is_critical: bool = False


class ClaimBrief(BaseModel):
    claim_id: str
    statement: str
    exact_quote: str
    source_date: Optional[str] = None


class LLMProvider(Protocol):
    def extract_claims(self, chunk: SourceChunk, known_item_ids: List[str]) -> ExtractionOutput:
        ...

    def assess_support(self, statement: str, quote: str) -> SupportAssessment:
        ...

    def compare_claims(self, claims: List[ClaimBrief]) -> Relation:
        ...


class FakeLLM:
    def __init__(self, mode: str = "normal"):
        self.mode = mode

    def extract_claims(self, chunk: SourceChunk, known_item_ids: List[str]) -> ExtractionOutput:
        if self.mode == "timeout":
            raise ContinuityException(ErrorCode.AI_UNAVAILABLE, "AI call timed out", status_code=503)
        if self.mode == "rate_limited":
            raise ContinuityException(ErrorCode.AI_UNAVAILABLE, "AI rate limit reached", status_code=503)
        if self.mode == "malformed_json":
            raise ContinuityException(ErrorCode.AI_BAD_OUTPUT, "Model output was invalid JSON", status_code=502)

        # Deterministic extraction based on content
        text = chunk.text
        text_lower = text.lower()
        claims: List[ExtractedClaimItem] = []

        # Synthetic Roomiez rules / general pattern extraction
        if "login authentication is incomplete" in text_lower:
            quote = "Login authentication is incomplete." if "Login authentication is incomplete." in text else "login authentication is incomplete"
            claims.append(ExtractedClaimItem(
                item_id="login_authentication",
                fact_type=FactType.STATUS,
                statement="Login authentication is incomplete.",
                owner=None,
                quotes=[QuoteItem(
                    source_id=str(uuid.uuid4()) if self.mode == "hallucinated_source" else chunk.source_id,
                    exact_quote="NOT_IN_TEXT_QUOTE" if self.mode == "quote_not_in_text" else quote,
                )],
                audience_roles=["backend_developer"],
            ))

        if "login authentication has been completed" in text_lower:
            quote = "Login authentication has been completed." if "Login authentication has been completed." in text else "login authentication has been completed"
            claims.append(ExtractedClaimItem(
                item_id="login_authentication",
                fact_type=FactType.STATUS,
                statement="Login authentication has been completed.",
                owner=None,
                quotes=[QuoteItem(source_id=chunk.source_id, exact_quote=quote)],
                audience_roles=["backend_developer"],
            ))

        if "password reset is blocked until the email service is configured" in text_lower:
            quote = "Password reset is blocked until the email service is configured." if "Password reset is blocked until the email service is configured." in text else "Password reset is blocked until the email service is configured"
            claims.append(ExtractedClaimItem(
                item_id="password_reset",
                fact_type=FactType.BLOCKER,
                statement="Password reset is blocked until the email service is configured.",
                owner=None,
                quotes=[QuoteItem(source_id=chunk.source_id, exact_quote=quote)],
                audience_roles=["backend_developer"],
            ))

        if "use jwt sessions instead of server sessions" in text_lower:
            quote = "use JWT sessions instead of server sessions" if "use JWT sessions instead of server sessions" in text else "Decision: use JWT sessions instead of server sessions"
            claims.append(ExtractedClaimItem(
                item_id="jwt_sessions",
                fact_type=FactType.DECISION,
                statement="Use JWT sessions instead of server sessions.",
                owner=None,
                quotes=[QuoteItem(source_id=chunk.source_id, exact_quote=quote)],
                audience_roles=["backend_developer"],
            ))

        if "who will configure the email service" in text_lower:
            quote = "Question: who will configure the email service?" if "Question: who will configure the email service?" in text else "who will configure the email service"
            claims.append(ExtractedClaimItem(
                item_id="email_service_configuration",
                fact_type=FactType.QUESTION,
                statement="Who will configure the email service?",
                owner=None,
                quotes=[QuoteItem(source_id=chunk.source_id, exact_quote=quote)],
                audience_roles=["backend_developer"],
            ))

        if "write end-to-end tests for login authentication" in text_lower:
            quote = "Next action: write end-to-end tests for login authentication." if "Next action: write end-to-end tests for login authentication." in text else "write end-to-end tests for login authentication"
            claims.append(ExtractedClaimItem(
                item_id="login_tests",
                fact_type=FactType.NEXT_ACTION,
                statement="Write end-to-end tests for login authentication.",
                owner="Ravi" if "ravi" in text_lower else None,
                quotes=[QuoteItem(source_id=chunk.source_id, exact_quote=quote)],
                audience_roles=["backend_developer"],
            ))

        if "tests need the staging environment" in text_lower:
            quote = "Dependency: tests need the staging environment." if "Dependency: tests need the staging environment." in text else "tests need the staging environment"
            claims.append(ExtractedClaimItem(
                item_id="login_tests",
                fact_type=FactType.DEPENDENCY,
                statement="Tests need the staging environment.",
                owner=None,
                quotes=[QuoteItem(source_id=chunk.source_id, exact_quote=quote)],
                audience_roles=["backend_developer"],
            ))

        if "ravi owns login testing" in text_lower:
            quote = "Ravi owns login testing; instructions are in docs/testing.md" if "Ravi owns login testing; instructions are in docs/testing.md" in text else "Ravi owns login testing"
            claims.append(ExtractedClaimItem(
                item_id="login_testing_ownership",
                fact_type=FactType.OWNER,
                statement="Ravi owns login testing and instructions are in docs/testing.md.",
                owner="Ravi",
                quotes=[QuoteItem(source_id=chunk.source_id, exact_quote=quote)],
                audience_roles=["backend_developer"],
            ))

        if "staging database is shared and may be reset" in text_lower:
            quote = "Risk: staging database is shared and may be reset." if "Risk: staging database is shared and may be reset." in text else "staging database is shared and may be reset"
            claims.append(ExtractedClaimItem(
                item_id="staging_database",
                fact_type=FactType.RISK,
                statement="Staging database is shared and may be reset.",
                owner=None,
                quotes=[QuoteItem(source_id=chunk.source_id, exact_quote=quote)],
                audience_roles=["backend_developer"],
            ))

        if "signup screen uses the blue primary button" in text_lower:
            quote = "Decision: signup screen uses the blue primary button." if "Decision: signup screen uses the blue primary button." in text else "signup screen uses the blue primary button"
            claims.append(ExtractedClaimItem(
                item_id="signup_button_color",
                fact_type=FactType.DECISION,
                statement="Signup screen uses the blue primary button.",
                owner=None,
                quotes=[QuoteItem(source_id=chunk.source_id, exact_quote=quote)],
                audience_roles=["designer"],
            ))

        if "signup mockups are approved" in text_lower:
            quote = "Status: signup mockups are approved." if "Status: signup mockups are approved." in text else "signup mockups are approved"
            claims.append(ExtractedClaimItem(
                item_id="signup_mockups",
                fact_type=FactType.STATUS,
                statement="Signup mockups are approved.",
                owner=None,
                quotes=[QuoteItem(source_id=chunk.source_id, exact_quote=quote)],
                audience_roles=["designer"],
            ))

        if "staging database password" in text_lower or "staging_db_password" in text_lower or "database connection password" in text_lower or ("password" in text_lower and "admin" in text_lower):
            # Fake credential note
            quote_line = [l.strip() for l in text.splitlines() if "password" in l.lower()][0]
            claims.append(ExtractedClaimItem(
                item_id="staging_db_credentials",
                fact_type=FactType.DECISION,
                statement=quote_line,
                owner=None,
                quotes=[QuoteItem(source_id=chunk.source_id, exact_quote=quote_line)],
                audience_roles=[],
            ))

        # Generic fallback for any arbitrary text chunk if no Roomiez matches found
        if not claims:
            # Extract first sentence as a status claim
            sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
            if sentences:
                s0 = sentences[0]
                quote = s0[:280]
                claims.append(ExtractedClaimItem(
                    item_id="project_general_status",
                    fact_type=FactType.STATUS,
                    statement=quote,
                    owner=None,
                    quotes=[QuoteItem(source_id=chunk.source_id, exact_quote=quote)],
                    audience_roles=[],
                ))

        return ExtractionOutput(claims=claims)

    def assess_support(self, statement: str, quote: str) -> SupportAssessment:
        if self.mode == "timeout":
            raise ContinuityException(ErrorCode.AI_UNAVAILABLE, "Support assessment timed out", status_code=503)
        # Check if statement is directly backed by quote
        norm_s = statement.lower().strip()
        norm_q = quote.lower().strip()
        if norm_q in norm_s or norm_s in norm_q or any(w in norm_s for w in norm_q.split()):
            return SupportAssessment(support_status=SupportStatus.SUPPORTS, note="Quote directly supports claim statement.")
        return SupportAssessment(support_status=SupportStatus.PARTIAL, note="Quote partially relates to statement.")

    def compare_claims(self, claims: List[ClaimBrief]) -> Relation:
        # Polarity keywords: complete/completed/done vs incomplete/pending/blocked
        statements = [c.statement.lower() for c in claims]
        has_done = any(any(k in s for k in ["complete", "completed", "done", "finished", "merged", "released"]) for s in statements)
        has_not_done = any(any(k in s for k in ["incomplete", "pending", "in progress", "not started", "blocked", "failing"]) for s in statements)

        if has_done and has_not_done:
            # Check for explicit supersession language in quotes
            superseding = False
            for c in claims:
                q = c.exact_quote.lower()
                if any(w in q for w in ["replaces", "supersedes", "updated to", "no longer", "changed to"]):
                    superseding = True
                    break
            if superseding:
                return Relation(
                    relation="explicit_supersession",
                    summary="Later record explicitly replaces earlier claim.",
                    is_critical=False,
                )
            return Relation(
                relation="contradiction",
                summary="Conflicting claims regarding completion state detected across sources.",
                is_critical=True,
            )

        # Check for explicit replacement
        for c in claims:
            q = c.exact_quote.lower()
            if any(w in q for w in ["replaces", "supersedes", "updated to", "no longer", "changed to"]):
                return Relation(
                    relation="possible_supersession",
                    summary="Explicit replacement language found in quote.",
                    is_critical=False,
                )

        return Relation(
            relation="unclear",
            summary="Ambiguous relation between statements; human review required.",
            is_critical=False,
        )


def get_llm_provider(mode: Optional[str] = None) -> LLMProvider:
    return FakeLLM(mode=mode or settings.LLM_PROVIDER)
