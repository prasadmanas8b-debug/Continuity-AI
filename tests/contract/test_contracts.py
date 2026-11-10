import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from app.schemas.enums import ErrorCode
from app.schemas.models import (
    Claim,
    ColdStartSummary,
    ColdStartTask,
    Conflict,
    Eligibility,
    ErrorEnvelope,
    Handover,
    HandoverDetail,
    ProjectSummary,
    ReviewResponse,
    Source,
)

EXAMPLES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "contracts", "examples"))


class TestContractExamples(unittest.TestCase):
    def load_json(self, filename):
        path = os.path.join(EXAMPLES_DIR, filename)
        self.assertTrue(os.path.exists(path), f"Example file {filename} does not exist")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_project_summary_example(self):
        data = self.load_json("project_summary.json")
        obj = ProjectSummary(**data)
        self.assertEqual(obj.project_id, data["project_id"])

    def test_source_pdf_example(self):
        data = self.load_json("source_pdf.json")
        obj = Source(**data)
        self.assertEqual(obj.source_id, data["source_id"])

    def test_claims_examples(self):
        c_ver = Claim(**self.load_json("claim_verified.json"))
        self.assertEqual(c_ver.verification_status.value, "verified")

        c_unc = Claim(**self.load_json("claim_uncertain.json"))
        self.assertEqual(c_unc.verification_status.value, "uncertain")

        c_no_ev = Claim(**self.load_json("claim_no_evidence.json"))
        self.assertEqual(c_no_ev.verification_status.value, "rejected")

        c_restr = Claim(**self.load_json("claim_restricted.json"))
        self.assertEqual(c_restr.sensitivity.value, "restricted")

    def test_conflict_examples(self):
        conf2 = Conflict(**self.load_json("conflict_two_claims.json"))
        self.assertEqual(len(conf2.claims), 2)
        self.assertTrue(conf2.is_critical)

        conf3 = Conflict(**self.load_json("conflict_three_claims.json"))
        self.assertEqual(len(conf3.claims), 3)

    def test_review_examples(self):
        r_acc = ReviewResponse(**self.load_json("review_accept.json"))
        self.assertEqual(r_acc.review.decision.value, "accept")

        r_edit = ReviewResponse(**self.load_json("review_edit.json"))
        self.assertEqual(r_edit.review.decision.value, "edit")

        r_stale = ErrorEnvelope(**self.load_json("review_stale_error.json"))
        self.assertEqual(r_stale.error.code, ErrorCode.STALE_VERSION.value)

    def test_handover_examples(self):
        h_draft = Handover(**self.load_json("handover_draft.json"))
        self.assertEqual(h_draft.status.value, "draft")

        h_back = HandoverDetail(**self.load_json("handover_detail_backend_developer.json"))
        self.assertEqual(h_back.recipient_role.value, "backend_developer")
        self.assertTrue(len(h_back.sections) > 0)

        h_des = HandoverDetail(**self.load_json("handover_detail_designer.json"))
        self.assertEqual(h_des.recipient_role.value, "designer")

        h_empty = self.load_json("handover_empty_permitted.json")
        self.assertEqual(h_empty, {"items": [], "total": 0})

    def test_eligibility_and_cold_start_examples(self):
        elig = Eligibility(**self.load_json("eligibility_blocked.json"))
        self.assertFalse(elig.can_approve_without_override)

        tasks_data = self.load_json("cold_start_tasks.json")
        tasks = [ColdStartTask(**t) for t in tasks_data]
        self.assertEqual(len(tasks), 3)

        summary = ColdStartSummary(**self.load_json("cold_start_summary.json"))
        self.assertEqual(summary.tasks_total, 3)

    def test_error_envelope_examples(self):
        for ec in ErrorCode:
            data = self.load_json(f"error_{ec.value.lower()}.json")
            envelope = ErrorEnvelope(**data)
            self.assertEqual(envelope.error.code, ec.value)


if __name__ == "__main__":
    unittest.main()
