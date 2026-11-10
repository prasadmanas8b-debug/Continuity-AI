import json
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from app.core.errors import ContinuityException
from app.db.session import db, get_utc_now
from app.extraction.llm_provider import get_llm_provider
from app.schemas.enums import QuoteMatchStatus, SupportStatus, VerificationStatus


def normalise_for_matching(text: str) -> Tuple[str, List[int]]:
    """Normalises text and returns (normalised_text, index_map).

    index_map[norm_idx] gives original character offset in raw text.
    Rules:
    - Unicode NFC
    - replace curly quotes and en/em dashes with straight equivalents
    - collapse whitespace runs (including newlines) to single space
    - trim (and track offset)
    - case-sensitive matching
    """
    nfc_text = unicodedata.normalize("NFC", text)
    # Character substitutions
    char_map = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
    }

    norm_chars = []
    idx_map = []
    in_whitespace = False

    for orig_idx, ch in enumerate(nfc_text):
        c = char_map.get(ch, ch)
        if c.isspace():
            if not in_whitespace:
                norm_chars.append(" ")
                idx_map.append(orig_idx)
                in_whitespace = True
        else:
            in_whitespace = False
            norm_chars.append(c)
            idx_map.append(orig_idx)

    # Trim leading and trailing whitespace while adjusting index map
    norm_str = "".join(norm_chars)
    l_strip = len(norm_str) - len(norm_str.lstrip(" "))
    r_strip = len(norm_str) - len(norm_str.rstrip(" "))

    if l_strip > 0:
        norm_str = norm_str[l_strip:]
        idx_map = idx_map[l_strip:]
    if r_strip > 0:
        norm_str = norm_str[:-r_strip]
        idx_map = idx_map[:-r_strip]

    return norm_str, idx_map


def find_quote_in_source(quote: str, source_text: str, page_offsets: List[int]) -> Optional[Dict[str, Any]]:
    if not quote.strip() or not source_text:
        return None

    norm_quote, _ = normalise_for_matching(quote)
    if not norm_quote:
        return None

    norm_source, idx_map = normalise_for_matching(source_text)

    # Find position
    start_pos = norm_source.find(norm_quote)
    if start_pos == -1:
        return None

    multiple_matches = norm_source.find(norm_quote, start_pos + 1) != -1

    orig_start = idx_map[start_pos]
    orig_end = idx_map[start_pos + len(norm_quote) - 1] + 1

    # Derive 1-indexed page from page_offsets
    page = 1
    for p_idx, offset in enumerate(page_offsets):
        if orig_start >= offset:
            page = p_idx + 1
        else:
            break

    locator = {
        "page": page,
        "char_start": orig_start,
        "char_end": orig_end,
    }
    return {
        "locator": locator,
        "multiple_matches": multiple_matches,
    }


def verify_claim_evidence(claim_id: str, provider=None) -> VerificationStatus:
    claim = db.query_one("SELECT * FROM claims WHERE claim_id = ?", (claim_id,))
    if not claim:
        return VerificationStatus.REJECTED

    evidence_rows = db.query_all("SELECT * FROM evidence WHERE claim_id = ?", (claim_id,))
    if not evidence_rows:
        # A claim with zero evidence rows is stored with verification_status = rejected
        with db.transaction() as cur:
            cur.execute(
                "UPDATE claims SET verification_status = ? WHERE claim_id = ?",
                (VerificationStatus.REJECTED.value, claim_id),
            )
        return VerificationStatus.REJECTED

    llm = provider or get_llm_provider()
    has_found_and_supports = False
    has_found = False

    with db.transaction() as cur:
        for ev in evidence_rows:
            source_id = ev["source_id"]
            quote = ev["exact_quote"]

            # Load source
            source = db.query_one(
                """
                SELECT s.source_id, s.project_id, s.ingestion_status, s.source_metadata, st.text, st.page_offsets 
                FROM sources s
                JOIN source_texts st ON s.source_id = st.source_id
                WHERE s.source_id = ?
                """,
                (source_id,),
            )

            # Check if source belongs to same project and is not archived
            if not source or source["project_id"] != claim["project_id"] or source["ingestion_status"] == "archived":
                cur.execute(
                    """
                    UPDATE evidence 
                    SET quote_match_status = ?, support_status = ?, support_note = ?
                    WHERE evidence_id = ?
                    """,
                    (QuoteMatchStatus.NOT_FOUND.value, SupportStatus.UNCHECKED.value, "Source not found or archived", ev["evidence_id"]),
                )
                continue

            page_offsets = json.loads(source["page_offsets"])
            meta = json.loads(source["source_metadata"]) if source.get("source_metadata") else {}

            match_result = find_quote_in_source(quote, source["text"], page_offsets)
            if not match_result:
                cur.execute(
                    """
                    UPDATE evidence 
                    SET quote_match_status = ?, support_status = ?, support_note = ?
                    WHERE evidence_id = ?
                    """,
                    (QuoteMatchStatus.NOT_FOUND.value, SupportStatus.UNCHECKED.value, "Quote not found in source text", ev["evidence_id"]),
                )
                continue

            has_found = True
            loc = match_result["locator"]
            if meta.get("path"):
                loc["path"] = meta["path"]
            if meta.get("commit_sha"):
                loc["commit_sha"] = meta["commit_sha"]

            note = "multiple matches" if match_result["multiple_matches"] else None

            # Question B: assess support
            try:
                assessment = llm.assess_support(claim["statement"], quote)
                supp_status = assessment.support_status
                if assessment.note:
                    note = f"{note}; {assessment.note}" if note else assessment.note
            except Exception:
                supp_status = SupportStatus.UNCHECKED

            if supp_status == SupportStatus.SUPPORTS:
                has_found_and_supports = True

            cur.execute(
                """
                UPDATE evidence 
                SET locator = ?, quote_match_status = ?, support_status = ?, support_note = ?
                WHERE evidence_id = ?
                """,
                (json.dumps(loc), QuoteMatchStatus.FOUND.value, supp_status.value, note, ev["evidence_id"]),
            )

        # Deterministic claim-level verification_status
        if has_found_and_supports:
            claim_v_status = VerificationStatus.VERIFIED
        elif has_found:
            claim_v_status = VerificationStatus.UNCERTAIN
        else:
            claim_v_status = VerificationStatus.REJECTED

        cur.execute(
            "UPDATE claims SET verification_status = ?, updated_at = ? WHERE claim_id = ?",
            (claim_v_status.value, get_utc_now(), claim_id),
        )

    return claim_v_status
