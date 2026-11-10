import projectSummary from '../../../contracts/examples/project_summary.json';
import sourcePdf from '../../../contracts/examples/source_pdf.json';
import claimVerified from '../../../contracts/examples/claim_verified.json';
import claimUncertain from '../../../contracts/examples/claim_uncertain.json';
import claimNoEvidence from '../../../contracts/examples/claim_no_evidence.json';
import claimRestricted from '../../../contracts/examples/claim_restricted.json';
import conflictTwoClaims from '../../../contracts/examples/conflict_two_claims.json';
import conflictThreeClaims from '../../../contracts/examples/conflict_three_claims.json';
import reviewAccept from '../../../contracts/examples/review_accept.json';
import reviewEdit from '../../../contracts/examples/review_edit.json';
import reviewStaleError from '../../../contracts/examples/review_stale_error.json';
import handoverDraft from '../../../contracts/examples/handover_draft.json';
import handoverDetailBackendDeveloper from '../../../contracts/examples/handover_detail_backend_developer.json';
import handoverDetailDesigner from '../../../contracts/examples/handover_detail_designer.json';
import handoverEmptyPermitted from '../../../contracts/examples/handover_empty_permitted.json';
import eligibilityBlocked from '../../../contracts/examples/eligibility_blocked.json';
import coldStartTasks from '../../../contracts/examples/cold_start_tasks.json';
import coldStartSummary from '../../../contracts/examples/cold_start_summary.json';

export const CONTRACT_FIXTURES = {
  projectSummary,
  sourcePdf,
  claimVerified,
  claimUncertain,
  claimNoEvidence,
  claimRestricted,
  conflictTwoClaims,
  conflictThreeClaims,
  reviewAccept,
  reviewEdit,
  reviewStaleError,
  handoverDraft,
  handoverDetailBackendDeveloper,
  handoverDetailDesigner,
  handoverEmptyPermitted,
  eligibilityBlocked,
  coldStartTasks,
  coldStartSummary,
};
