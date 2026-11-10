from enum import Enum


class UserRole(str, Enum):
    MANAGER = "manager"
    CONTRIBUTOR = "contributor"
    INCOMING_MEMBER = "incoming_member"


class RecipientRole(str, Enum):
    BACKEND_DEVELOPER = "backend_developer"
    DESIGNER = "designer"


class SourceType(str, Enum):
    GITHUB = "github"
    PDF = "pdf"
    TXT = "txt"
    MD = "md"
    DOCX = "docx"  # reserved
    TASK_EXPORT = "task_export"  # reserved


class IngestionStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    ARCHIVED = "archived"


class Sensitivity(str, Enum):
    NORMAL = "normal"
    RESTRICTED = "restricted"


class FactType(str, Enum):
    DECISION = "decision"
    OWNER = "owner"
    STATUS = "status"
    BLOCKER = "blocker"
    DEPENDENCY = "dependency"
    RISK = "risk"
    NEXT_ACTION = "next_action"
    QUESTION = "question"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


class ConflictStatus(str, Enum):
    NONE = "none"
    CONFLICT = "conflict"
    SUPERSEDED = "superseded"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


class QuoteMatchStatus(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    UNCHECKED = "unchecked"


class SupportStatus(str, Enum):
    SUPPORTS = "supports"
    PARTIAL = "partial"
    DOES_NOT_SUPPORT = "does_not_support"
    UNCHECKED = "unchecked"


class ConflictType(str, Enum):
    CONTRADICTION = "contradiction"
    POSSIBLE_SUPERSESSION = "possible_supersession"
    MISSING_INFORMATION = "missing_information"


class ConflictRecordStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


class ReviewDecision(str, Enum):
    ACCEPT = "accept"
    EDIT = "edit"
    REJECT = "reject"
    UNRESOLVED = "unresolved"


class HandoverStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    SHARED = "shared"  # reserved
    REVOKED = "revoked"


class ExtractionRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ColdStartOutcome(str, Enum):
    PASS = "pass"
    NEEDS_HELP = "needs_help"


class UncertaintyLabel(str, Enum):
    NONE = "none"
    UNCERTAIN = "uncertain"
    UNRESOLVED = "unresolved"
    CONFLICTED = "conflicted"


class SectionKey(str, Enum):
    CURRENT_STATUS = "current_status"
    DECISIONS = "decisions"
    RESPONSIBILITIES = "responsibilities"
    BLOCKERS_DEPENDENCIES = "blockers_dependencies"
    RISKS = "risks"
    NEXT_ACTIONS = "next_actions"
    UNRESOLVED_QUESTIONS = "unresolved_questions"


class ErrorCode(str, Enum):
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    HANDOVER_REVOKED = "HANDOVER_REVOKED"
    NOT_FOUND = "NOT_FOUND"
    STALE_VERSION = "STALE_VERSION"
    DUPLICATE_SOURCE = "DUPLICATE_SOURCE"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    EXTRACTION_IN_PROGRESS = "EXTRACTION_IN_PROGRESS"
    APPROVAL_BLOCKED_CONFLICT = "APPROVAL_BLOCKED_CONFLICT"
    HANDOVER_IMMUTABLE = "HANDOVER_IMMUTABLE"
    HANDOVER_NOT_APPROVED = "HANDOVER_NOT_APPROVED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    EMPTY_FILE = "EMPTY_FILE"
    CORRUPT_FILE = "CORRUPT_FILE"
    NO_EXTRACTABLE_TEXT = "NO_EXTRACTABLE_TEXT"
    CLAIM_NOT_ACCEPTABLE = "CLAIM_NOT_ACCEPTABLE"
    GITHUB_URL_INVALID = "GITHUB_URL_INVALID"
    GITHUB_RATE_LIMITED = "GITHUB_RATE_LIMITED"
    GITHUB_UNAVAILABLE = "GITHUB_UNAVAILABLE"
    AI_BAD_OUTPUT = "AI_BAD_OUTPUT"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"
    STORAGE_UNAVAILABLE = "STORAGE_UNAVAILABLE"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
