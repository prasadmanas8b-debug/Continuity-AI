# Contracts Changelog

All changes to API schemas, field names, enums, error codes, and permission rules are tracked here.

## [1.0.0] - 2026-11-09
### Baseline Release
- Initial baseline for Round 2 Master Development Specification (frozen by Manas & Anant).
- Reconciled earlier drafts:
  - Review concurrency switched to integer `version` / `expected_version`.
  - Evidence records have distinct `quote_match_status` and `support_status`.
  - Added `audience_roles` on sources and claims for role-based handover filtering.
  - Removed `source_ids` array on claim; derived from `evidence[].source_id`.
  - Standardized on `sensitivity` (normal, restricted).
  - Standardized cold-start fields: `outcome` and `time_seconds`.
  - Defined `HandoverClaim` snapshot schema with `uncertainty_label`.
  - Added Appendix A addenda (A1 - A12).
