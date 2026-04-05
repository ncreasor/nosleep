"""Reference demo contracts that must not be deleted."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schemas import DocumentResponse

PROTECTED_FILENAMES = frozenset(
    {
        "contract_real_2026.txt",
        "contract_outdated_2020.txt",
    }
)


def is_reference_contract_protected(doc) -> bool:
    fn = (getattr(doc, "filename", None) or "").strip()
    if fn in PROTECTED_FILENAMES:
        return True
    title = getattr(doc, "title", None) or ""
    if "РЕАЛЬНЫЙ" in title and "2026" in title:
        return True
    if "УСТАРЕВШИЙ" in title and "2020" in title:
        return True
    return False


def document_to_response(doc) -> "DocumentResponse":
    from schemas import DocumentResponse

    r = DocumentResponse.model_validate(doc)
    return r.model_copy(update={"protected": is_reference_contract_protected(doc)})
