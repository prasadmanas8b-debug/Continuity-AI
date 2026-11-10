# Continuity AI - Architecture & Technical Specification

## 1. System Overview
Continuity AI is an evidence-first knowledge handover platform that extracts, structures, verifies, and shares institutional project knowledge when team members transition roles. Rather than relying on ungrounded AI text generation, Continuity AI operates as a deterministic, audited pipeline enforcing strict evidence linkage, conflict surfacing, and role-based permissions.

```
+-----------------------------------------------------------------------------------+
|                                 Continuity AI                                     |
+-----------------------------------------------------------------------------------+
|  [Connect] Ingestion: PDF (pypdf), Text, GitHub REST API -> SHA-256 deduplication |
|                                       v                                           |
|  [Reconstruct] Extraction: LLMProvider chunking, v1 prompt, JSON schema validation |
|                                       v                                           |
|  [Verify] Verification: Deterministic NFC quote match (Question A) + Support (B)  |
|                                       v                                           |
|  [Detect] Conflicts & Gaps: Polarity clustering, supersession check, G1/G2 gaps    |
|                                       v                                           |
|  [Review] Human Review: Optimistic concurrency (expected_version), audit log      |
|                                       v                                           |
|  [Handover] Permissions & Snapshots: Policy filtering, approval gate, immutability|
|                                       v                                           |
|  [Test] Cold-Start: Deterministic tasks, answer-key isolation, newcomer metrics   |
+-----------------------------------------------------------------------------------+
```

---

## 2. Core Trust Invariants
1. **T1 Candidate Claims**: AI output is strictly candidate data. It is never the source of truth.
2. **T2 Independent Statuses**: `verification_status`, `conflict_status`, and `review_status` are managed as separate, independent fields. Permissions (`sensitivity`, `audience_roles`) form a fourth independent dimension.
3. **T3 Existence != Truth**: Finding an exact quote proves only that the text exists in the source; it does not prove the fact is true in the real world.
4. **T4 Timestamp Never Decides**: Newer dates never automatically override older records without explicit replacement language.
5. **T5 Original Wording Preserved**: AI wording is stored permanently in `original_statement`. Edits modify `statement`, increment `version`, and record a history row in `reviews`.
6. **T6 Snapshot Immutability**: Approved handovers and their claims are immutable snapshots.
7. **T7 Backend Security**: Role permissions, sensitivity filters, and audience filtering are strictly evaluated in backend services before serialization.
8. **T8 Transparent Uncertainty**: Contradictions, missing owners, and unverified claims are surfaced clearly rather than hidden or smoothed over.
9. **T9 Honest Reporting**: Failures and partial imports report exact errors without fake success states.
10. **T10 Zero Secret Leakage**: Confidential sources and credentials are never leaked in error envelopes, logs, or unpermitted role views.

---

## 3. Database Schema Design
- **Primary & Foreign Keys**: UUID strings across all relational tables.
- **Timestamps**: `TIMESTAMPTZ` formatted as ISO-8601 UTC strings (`YYYY-MM-DDTHH:MM:SSZ`).
- **Enums & Constraints**: Check constraints mirror Pydantic models at the database level for defense-in-depth.
- **Append-Only Tables**: `reviews` and `audit_log` tables reject in-place updates.

---

## 4. Cold-Start Testing Methodology
The Cold-Start module measures whether an incoming team member can effectively ramp up using only the handover artifact:
- **Task 1**: Status retrieval and evidence navigation.
- **Task 2**: Next action identification and dependency mapping.
- **Task 3**: Activity ownership and onboarding instruction discovery.
- **Answer-Key Protection**: `expected_reference` criteria are stored only on the server, ensuring tests measure genuine handover quality without test compromise.
