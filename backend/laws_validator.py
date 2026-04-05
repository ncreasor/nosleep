import json
import re
from pathlib import Path
from typing import Optional

# Load the Kazakh laws database
LAWS_DB_PATH = Path(__file__).parent / "kazakh_laws_db.json"
with open(LAWS_DB_PATH, 'r', encoding='utf-8') as f:
    LAWS_DB = json.load(f)

# Map of common law abbreviations to codes (nominative + genitive + instrumental forms)
LAW_ABBREVIATIONS = {
    'ТК РК': 'ТК РК',
    'Трудовой кодекс': 'ТК РК',
    'Трудового кодекса': 'ТК РК',
    'Трудового кодекса Республики Казахстан': 'ТК РК',
    'Трудовым кодексом': 'ТК РК',
    'ГК РК': 'ГК РК',
    'Гражданский кодекс': 'ГК РК',
    'Гражданского кодекса': 'ГК РК',
    'Гражданского кодекса РК': 'ГК РК',
    'Гражданского кодекса Республики Казахстан': 'ГК РК',
    'Гражданским кодексом': 'ГК РК',
    'УК РК': 'УК РК',
    'Уголовный кодекс': 'УК РК',
    'Уголовного кодекса': 'УК РК',
    'Уголовного кодекса РК': 'УК РК',
    'НК РК': 'НК РК',
    'Налоговый кодекс': 'НК РК',
    'Налогового кодекса': 'НК РК',
    'Налогового кодекса РК': 'НК РК',
    'ГПК РК': 'ГПК РК',
    'Гражданский процессуальный кодекс': 'ГПК РК',
    'Гражданского процессуального кодекса': 'ГПК РК',
    'УПК РК': 'УПК РК',
    'Уголовно-процессуальный кодекс': 'УПК РК',
    'Уголовно-процессуального кодекса': 'УПК РК',
    'КоАП РК': 'КоАП РК',
    'Кодекс об административных правонарушениях': 'КоАП РК',
    'Кодекса об административных правонарушениях': 'КоАП РК',
    'ЖК РК': 'ЖК РК',
    'Жилищный кодекс': 'ЖК РК',
    'Жилищного кодекса': 'ЖК РК',
    'СК РК': 'СК РК',
    'Семейный кодекс': 'СК РК',
    'Семейного кодекса': 'СК РК',
    'ЗК РК': 'ЗК РК',
    'Земельный кодекс': 'ЗК РК',
    'Земельного кодекса': 'ЗК РК',
}


def parse_norm_reference(norm_text: str) -> Optional[tuple[str, str]]:
    """
    Parse a norm reference like "ст. 293 ТК РК" or "статья 50 ТК РК"
    Returns: (law_code, article_number) or None
    """
    # Pattern: "ст." or "статья" followed by number and law code
    pattern = r'(?:ст\.|статья|статьей)\s+(\d+)\s+(.+)'
    match = re.search(pattern, norm_text, re.IGNORECASE)

    if match:
        article_num = match.group(1)
        law_part = match.group(2).strip()

        # Try exact match first, then progressively shorter prefixes
        law_code = LAW_ABBREVIATIONS.get(law_part)
        if not law_code:
            # Try matching against known abbreviation keys (longest match first)
            for abbr in sorted(LAW_ABBREVIATIONS.keys(), key=len, reverse=True):
                if law_part.lower().startswith(abbr.lower()):
                    law_code = LAW_ABBREVIATIONS[abbr]
                    break
        if not law_code:
            law_code = law_part
        return (law_code, article_num)

    return None


def validate_norm(norm_text: str) -> dict:
    """
    Validate if a norm exists in the database
    Returns dict with validation result
    """
    parsed = parse_norm_reference(norm_text)

    if not parsed:
        return {
            "norm_text": norm_text,
            "status": "invalid",
            "title": None,
            "reason": "Could not parse norm reference",
            "introduced": None,
            "valid": False,
        }

    law_code, article_num = parsed

    # Check if law code exists
    if law_code not in LAWS_DB:
        return {
            "norm_text": norm_text,
            "status": "invalid",
            "title": None,
            "reason": f"Unknown law code: {law_code}",
            "introduced": None,
            "valid": False,
        }

    law_data = LAWS_DB[law_code]

    # Check if article exists
    if article_num not in law_data["articles"]:
        return {
            "norm_text": norm_text,
            "status": "invalid",
            "title": None,
            "reason": f"Article {article_num} not found in {law_code}",
            "introduced": law_data.get("introduced"),
            "valid": False,
        }

    article_data = law_data["articles"][article_num]

    return {
        "norm_text": norm_text,
        "status": article_data.get("status", "valid"),
        "title": article_data.get("title"),
        "law_code": law_code,
        "article_num": article_num,
        "law_name": law_data.get("code_name"),
        "reason": None,
        "introduced": law_data.get("introduced"),
        "valid": True,
    }


def validate_articles(articles: list[dict]) -> list[dict]:
    """
    Validate a list of articles extracted by GPT
    Updates their status based on actual law database
    """
    validated = []

    for article in articles:
        norm_text = article.get("norm_text", "")
        validation = validate_norm(norm_text)

        if not validation["valid"]:
            # Mark as invalid if not found in database
            article["status"] = "invalid"
            article["title"] = f"Не найдена в базе ({norm_text})"
        else:
            # Use real data from database
            article["status"] = validation["status"]
            if not article.get("title"):
                article["title"] = validation["title"]

        validated.append(article)

    return validated
