# Continuity AI - Progress & Changes From Round 1

This document records the architectural improvements, contract evolutions, and engineering enhancements delivered in Round 2.

## Key Changes & Refinements

### 1. Concurrency Model: Integer Versioning
- **Round 1 Concept**: Optimistic locking based on timestamps (`expected_updated_at`).
- **Round 2 Improvement (Decision D-11)**: Replaced timestamp checking with an integer `version` field on each claim and `expected_version` on reviews. Eliminates subtle millisecond rounding bugs across database engines and guarantees atomic detection of concurrent reviewer actions (409 `STALE_VERSION`).

### 2. Dual-Status Evidence Verification
- **Round 1 Concept**: Single `support_status` flag on evidence.
- **Round 2 Improvement**: Decoupled evidence verification into two distinct, independent questions:
  1. **Question A (Quote Existence - Deterministic)**: Checks if the exact quote exists in the source text using Unicode NFC normalisation, quotation mark and dash standardisation, whitespace collapsing, and returns exact character locator offsets.
  2. **Question B (Semantic Support - LLM Assisted)**: Evaluates whether the identified quote genuinely supports the statement (`supports`, `partial`, `does_not_support`).

### 3. Separation of Independent Concern Axes (Trust Invariant T2)
- Replaced ambiguous blended statuses with four strictly independent concepts:
  - `verification_status` (`verified`, `uncertain`, `rejected`)
  - `conflict_status` (`none`, `conflict`, `superseded`)
  - `review_status` (`pending`, `accepted`, `edited`, `rejected`, `unresolved`)
  - `permissions / sensitivity` (`normal`, `restricted`, `audience_roles`)

### 4. No Timestamp Winner Rule for Conflicts (Trust Invariant T4)
- **Round 1 Risk**: AI summary choosing the latest statement as truth.
- **Round 2 Enforcement**: Newer dates never decide a conflict automatically. Explicit replacement language (e.g., "replaces", "supersedes", "updated to") is required in the source quote to flag possible supersession; otherwise, contradictory statements are preserved side-by-side as an active conflict requiring human review.

### 5. Snapshot Immutability (Trust Invariant T6)
- Approved handovers are saved as frozen snapshots in dedicated `handover_claims` records. Later claim edits or reviews do not mutate approved handovers, guaranteeing that incoming members see a consistent, version-controlled view.

### 6. Answer-Key Protection in Cold-Start Tests
- In Round 1, candidate answer criteria could be exposed to frontend components. In Round 2, `expected_reference` is strictly stored server-side on `cold_start_tasks` and is never serialized to the client.
