import re
from html import escape


_PLACEHOLDER_RE = re.compile(r"\{\{([^}]+)\}\}")


def inject_placeholder_spans(text: str) -> str:
    """Replace {{var_id}} with visible blanks; escape plain text."""
    if not text:
        return ""
    parts = _PLACEHOLDER_RE.split(text)
    out: list[str] = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            out.append(escape(part).replace("\n", "<br>"))
        else:
            vid = part.strip()
            safe = escape(vid)
            out.append(
                f'<span data-template-var="{safe}" class="template-placeholder" title="{safe}">__________</span>'
            )
    return "".join(out)


def sections_to_editor_html(template_json: dict) -> str:
    """Turn LLM sections into HTML for the rich template editor."""
    sections = template_json.get("sections") or []
    if not sections:
        return "<p><br></p>"
    try:
        sections = sorted(sections, key=lambda s: (s.get("order") is None, s.get("order", 0)))
    except TypeError:
        pass
    blocks: list[str] = []
    for sec in sections:
        title = (sec.get("title") or "").strip()
        body = sec.get("content") or ""
        if title:
            blocks.append(
                f'<p class="template-section-title"><strong>{escape(title)}</strong></p>'
            )
        for para in body.split("\n\n"):
            p = para.strip()
            if not p:
                continue
            inner = inject_placeholder_spans(p)
            blocks.append(f"<p>{inner}</p>")
    return "".join(blocks) if blocks else "<p><br></p>"


def pack_template_content(template_json: dict) -> dict:
    """Stored in Template.content as JSON: editor HTML + structured metadata for forms."""
    html = sections_to_editor_html(template_json)
    return {
        "format": "rich_html",
        "html": html,
        "structured": template_json,
    }
