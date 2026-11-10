import io
import unicodedata
from typing import List, Tuple
from pypdf import PdfReader

from app.core.errors import ContinuityException
from app.schemas.enums import ErrorCode


def extract_pdf_text_and_offsets(pdf_bytes: bytes) -> Tuple[str, List[int]]:
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ContinuityException(
            code=ErrorCode.UNSUPPORTED_FILE_TYPE,
            message="File does not have valid PDF header",
            status_code=415,
        )
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        if len(reader.pages) == 0:
            raise ContinuityException(
                code=ErrorCode.EMPTY_FILE,
                message="PDF has zero pages",
                status_code=422,
            )
        full_text_parts = []
        page_offsets = []
        current_offset = 0

        for page in reader.pages:
            page_text = page.extract_text() or ""
            # Normalise line endings to \n and Unicode to NFC
            page_text = page_text.replace("\r\n", "\n").replace("\r", "\n")
            page_text = unicodedata.normalize("NFC", page_text)
            page_offsets.append(current_offset)
            full_text_parts.append(page_text)
            current_offset += len(page_text)

        full_text = "".join(full_text_parts)
        if not full_text.strip():
            raise ContinuityException(
                code=ErrorCode.NO_EXTRACTABLE_TEXT,
                message="No readable text found in PDF. Scanned PDFs are not supported yet.",
                status_code=422,
            )
        return full_text, page_offsets
    except ContinuityException:
        raise
    except Exception as e:
        raise ContinuityException(
            code=ErrorCode.CORRUPT_FILE,
            message="Unreadable PDF file",
            status_code=422,
        )


def extract_text_file_and_offsets(raw_bytes: bytes, filename: str) -> Tuple[str, List[int]]:
    if b"\x00" in raw_bytes:
        raise ContinuityException(
            code=ErrorCode.UNSUPPORTED_FILE_TYPE,
            message="Binary content detected in text file",
            status_code=415,
        )
    try:
        # UTF-8 decode (accept BOM)
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ContinuityException(
            code=ErrorCode.UNSUPPORTED_FILE_TYPE,
            message="Text file could not be decoded as UTF-8",
            status_code=415,
        )
    # Normalise line endings to \n and Unicode to NFC
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)
    if not text.strip():
        raise ContinuityException(
            code=ErrorCode.NO_EXTRACTABLE_TEXT,
            message="Text file is empty or contains only whitespace",
            status_code=422,
        )
    return text, [0]
