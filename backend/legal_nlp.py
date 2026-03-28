import logging
import re
from typing import Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EntityType(Enum):
    """Legal document entity types."""
    PERSON = "person"
    ORGANIZATION = "organization"
    DATE = "date"
    AMOUNT = "amount"
    LEGAL_TERM = "legal_term"
    ARTICLE = "article"
    LAW_REFERENCE = "law_reference"
    DEFINITION = "definition"


@dataclass
class Entity:
    """Extracted entity."""
    type: EntityType
    text: str
    start: int
    end: int
    confidence: float = 1.0


@dataclass
class Relation:
    """Relation between entities."""
    source: str
    target: str
    relation_type: str
    confidence: float = 1.0


@dataclass
class DocumentSection:
    """Structured document section."""
    level: int  # 0=chapter, 1=article, 2=subsection
    title: str
    content: str
    section_type: str  # "chapter", "article", "subsection", "note", "definition"
    number: Optional[str] = None
    entities: list[Entity] = None
    parent_number: Optional[str] = None

    def __post_init__(self):
        if self.entities is None:
            self.entities = []


class LegalNER:
    """Named Entity Recognition for legal documents."""

    # Patterns for different entity types
    PERSON_PATTERNS = [
        r'(?P<person>Г-н[а]?\s+[А-Яа-я]+\s+[А-Яа-я]+)',  # Mr./Mrs. + Name
        r'(?P<person>[А-Яа-я]+\s+[А-Яа-я]+\s+[А-Яа-я]+)',  # Full name (3+ words with caps)
    ]

    ORGANIZATION_PATTERNS = [
        r'(?P<org>\b[А-Я][А-Яа-я]+(?:\s+[А-Яа-я]+)*\s+(?:АО|ООО|ОДО|ИП)\b)',
        r'(?P<org>(?:Министерство|Агентство|Комитет|Управление|Офис)\s+[А-Яа-я\s]+)',
    ]

    DATE_PATTERNS = [
        r'(?P<date>\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4})',
        r'(?P<date>\d{1,2}\.\d{1,2}\.\d{4})',
        r'(?P<date>\d{4}-\d{1,2}-\d{1,2})',
    ]

    AMOUNT_PATTERNS = [
        r'(?P<amount>\d+\s*(?:млн|млрд|тыс)?\.?\s*(?:тенге|USD|EUR|долларов|евро))',
        r'(?P<amount>\d+(?:\s*\d{3})*(?:\.\d{1,2})?\s*(?:тг|т\.|€|\$|₸))',
    ]

    LAW_REFERENCE_PATTERNS = [
        r'(?P<law_ref>Закон\s+(?:РК\s+)?№\s*[\d\-]+)',
        r'(?P<law_ref>Кодекс\s+(?:РК\s+)?[А-Яа-я\s]+)',
        r'(?P<law_ref>Указ\s+Президента\s+(?:РК\s+)?№\s*[\d\-]+)',
    ]

    ARTICLE_PATTERNS = [
        r'(?P<article>(?:Статья|ст\.|ст)\s+\d+(?:\.\d+)*)',
        r'(?P<article>(?:пункт|п\.|п)\s+\d+(?:\.\d+)*)',
        r'(?P<article>(?:подпункт|пп\.|пп)\s+\d+(?:\.\d+)*)',
    ]

    @classmethod
    def extract_entities(cls, text: str) -> list[Entity]:
        """Extract named entities from legal text."""
        entities = []

        # Extract persons
        for pattern in cls.PERSON_PATTERNS:
            for match in re.finditer(pattern, text):
                entities.append(
                    Entity(
                        type=EntityType.PERSON,
                        text=match.group(),
                        start=match.start(),
                        end=match.end(),
                    )
                )

        # Extract organizations
        for pattern in cls.ORGANIZATION_PATTERNS:
            for match in re.finditer(pattern, text):
                entities.append(
                    Entity(
                        type=EntityType.ORGANIZATION,
                        text=match.group(),
                        start=match.start(),
                        end=match.end(),
                    )
                )

        # Extract dates
        for pattern in cls.DATE_PATTERNS:
            for match in re.finditer(pattern, text):
                entities.append(
                    Entity(
                        type=EntityType.DATE,
                        text=match.group(),
                        start=match.start(),
                        end=match.end(),
                    )
                )

        # Extract amounts
        for pattern in cls.AMOUNT_PATTERNS:
            for match in re.finditer(pattern, text):
                entities.append(
                    Entity(
                        type=EntityType.AMOUNT,
                        text=match.group(),
                        start=match.start(),
                        end=match.end(),
                    )
                )

        # Extract law references
        for pattern in cls.LAW_REFERENCE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.append(
                    Entity(
                        type=EntityType.LAW_REFERENCE,
                        text=match.group(),
                        start=match.start(),
                        end=match.end(),
                    )
                )

        # Extract articles
        for pattern in cls.ARTICLE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.append(
                    Entity(
                        type=EntityType.ARTICLE,
                        text=match.group(),
                        start=match.start(),
                        end=match.end(),
                    )
                )

        # Remove duplicates and sort
        unique_entities = {}
        for entity in entities:
            key = (entity.start, entity.end)
            if key not in unique_entities:
                unique_entities[key] = entity

        return sorted(
            unique_entities.values(),
            key=lambda e: (e.start, e.end),
        )


class RelationExtractor:
    """Extract relations between entities."""

    RELATION_PATTERNS = [
        (
            r'(?P<source>ст\.\s+\d+(?:\.\d+)*)\s+(?:ссылается на|относится к|следует из|основывается на|в соответствии с|в соответствии из)\s+(?P<target>(?:Закон|Кодекс|Указ)[^.]*?(?:№\s*[\d\-]+)?)',
            "references",
        ),
        (
            r'(?P<source>ст\.\s+\d+(?:\.\d+)*)\s+(?:противоречит|несовместима с|конфликтует с)\s+(?P<target>(?:ст\.\s+\d+(?:\.\d+)*|Закон[^.]*?))',
            "contradicts",
        ),
        (
            r'(?P<source>(?:Закон|Кодекс)[^.]*?(?:№\s*[\d\-]+)?)\s+(?:отменяет|аннулирует|отменяет действие)\s+(?P<target>(?:Закон|Кодекс)[^.]*?(?:№\s*[\d\-]+)?)',
            "repeals",
        ),
    ]

    @classmethod
    def extract_relations(cls, text: str) -> list[Relation]:
        """Extract relations between entities."""
        relations = []

        for pattern, relation_type in cls.RELATION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    source = match.group("source").strip()
                    target = match.group("target").strip()
                    relations.append(
                        Relation(
                            source=source,
                            target=target,
                            relation_type=relation_type,
                        )
                    )
                except IndexError:
                    continue

        return relations


class DocumentParser:
    """Parse legal document structure."""

    # Section detection patterns
    CHAPTER_PATTERN = r'^\s*(?:ГЛАВА|РАЗДЕЛ|ЧАСТЬ|КНИГА)\s+([IVX\d]+)\.?\s*(.+)$'
    ARTICLE_PATTERN = r'^\s*(?:Статья|ст\.|ст)\s+(\d+(?:\.\d+)*)\s*\.?\s*(.+?)$'
    SUBSECTION_PATTERN = r'^\s*(?:\d+\.|[а-я]\))\s+(.+?)$'
    DEFINITION_PATTERN = r'^\s*"(.+?)"\s*-\s*(.+?)$'

    @classmethod
    def parse(cls, text: str) -> list[DocumentSection]:
        """Parse document into structured sections."""
        lines = text.split('\n')
        sections = []
        current_chapter = None
        current_article = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for chapter
            chapter_match = re.match(cls.CHAPTER_PATTERN, line, re.IGNORECASE)
            if chapter_match:
                current_chapter = DocumentSection(
                    level=0,
                    title=chapter_match.group(2),
                    content=line,
                    section_type="chapter",
                    number=chapter_match.group(1),
                )
                sections.append(current_chapter)
                current_article = None
                continue

            # Check for article
            article_match = re.match(cls.ARTICLE_PATTERN, line, re.IGNORECASE)
            if article_match:
                current_article = DocumentSection(
                    level=1,
                    title=article_match.group(2),
                    content=line,
                    section_type="article",
                    number=article_match.group(1),
                    parent_number=current_chapter.number if current_chapter else None,
                )
                sections.append(current_article)
                continue

            # Check for subsection
            if current_article and re.match(cls.SUBSECTION_PATTERN, line):
                subsection = DocumentSection(
                    level=2,
                    title=line,
                    content=line,
                    section_type="subsection",
                    parent_number=current_article.number,
                )
                sections.append(subsection)
                continue

            # Add content to current section
            if current_article:
                current_article.content += f"\n{line}"
            elif current_chapter:
                current_chapter.content += f"\n{line}"

        # Extract entities for each section
        for section in sections:
            section.entities = LegalNER.extract_entities(section.content)

        return sections

    @classmethod
    def get_toc(cls, sections: list[DocumentSection]) -> dict:
        """Generate table of contents from parsed sections."""
        toc = {"chapters": []}

        current_chapter = None
        for section in sections:
            if section.section_type == "chapter":
                current_chapter = {
                    "number": section.number,
                    "title": section.title,
                    "articles": [],
                }
                toc["chapters"].append(current_chapter)
            elif section.section_type == "article" and current_chapter:
                current_chapter["articles"].append(
                    {"number": section.number, "title": section.title}
                )

        return toc


class DefinitionExtractor:
    """Extract key terms and definitions from documents."""

    @classmethod
    def extract_definitions(cls, text: str) -> dict[str, str]:
        """Extract term definitions."""
        definitions = {}

        # Pattern: "Term" - definition
        pattern = r'"([^"]+)"\s*-\s*(.+?)(?=\n"|$)'
        for match in re.finditer(pattern, text, re.MULTILINE | re.DOTALL):
            term = match.group(1).strip()
            definition = match.group(2).strip().replace('\n', ' ')
            definitions[term] = definition

        # Pattern: Term means/is/shall be definition
        pattern = r'\b(\w+)\s+(?:means|is|shall be)\s+(.+?)(?=\n|[.;])'
        for match in re.finditer(pattern, text, re.IGNORECASE):
            term = match.group(1).strip()
            definition = match.group(2).strip()
            if len(term) < 50:  # Filter out false positives
                definitions[term] = definition

        return definitions
