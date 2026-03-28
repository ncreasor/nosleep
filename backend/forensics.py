import logging
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
import re
import os

logger = logging.getLogger(__name__)


@dataclass
class ForensicFinding:
    """A forensic analysis finding."""
    category: str  # "signature", "metadata", "content", "structure"
    severity: str  # "high", "medium", "low"
    finding: str
    details: str
    recommendation: str


@dataclass
class ForensicReport:
    """Complete forensic analysis report."""
    overall_risk_score: float  # 0-1, 1 = likely forged
    risk_level: str  # "low", "medium", "high", "critical"
    authenticity_confidence: float  # 0-1, how confident this is genuine
    findings: list[ForensicFinding]
    summary: str
    recommendations: list[str]


class DocumentForensics:
    """Analyze documents for forgery indicators."""

    # Suspicious patterns
    SUSPICIOUS_PATTERNS = {
        "inconsistent_dates": r'(\d{1,2}[\./\-]\d{1,2}[\./\-]\d{4}).*?(\d{1,2}[\./\-]\d{1,2}[\./\-]\d{4})',
        "fake_signature_markers": r'(?:подпись|signature).*?\(.*?\)',  # Signature in parentheses
        "copy_paste_indicators": r'XXX|ZZZ|\[signature\]|\[seal\]|\[date\]',
        "placeholder_text": r'\[.*?\]|\{.*?\}|<<.*?>>',
        "artificial_numbering": r'(?:ст\.|статья)\s+(?:\d{1,2}\.?){4,}',  # Unusually formatted articles
    }

    # Patterns that indicate structure issues
    STRUCTURE_ISSUES = {
        "missing_jurisdiction": r'(?!.*(?:казахстан|kazakhstan|рк|kz))',
        "invalid_law_references": r'Закон\s+№\s*\d{1,2}(?!\-)',  # Law number too short
        "inconsistent_terminology": r'(?P<term1>гражданское право|civil law).*?(?P<term2>уголовное право|criminal law).*?\1',
    }

    @staticmethod
    def _extract_dates(text: str) -> list[str]:
        """Extract all dates from document."""
        patterns = [
            r'\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}',
            r'\d{1,2}\.\d{1,2}\.\d{4}',
            r'\d{4}-\d{1,2}-\d{1,2}',
        ]
        dates = []
        for pattern in patterns:
            dates.extend(re.findall(pattern, text, re.IGNORECASE))
        return dates

    @staticmethod
    def _extract_signatures(text: str) -> list[tuple]:
        """Extract signature markers and their positions."""
        pattern = r'(?:подпись|signature|подписано|signed)[:\s]+([^\n]*)'
        return re.findall(pattern, text, re.IGNORECASE)

    @staticmethod
    def _analyze_metadata(file_path: str) -> dict:
        """Analyze file metadata."""
        findings = []

        if not os.path.exists(file_path):
            return {
                "findings": findings,
                "file_exists": False,
            }

        try:
            stat = os.stat(file_path)
            created_time = datetime.fromtimestamp(stat.st_ctime)
            modified_time = datetime.fromtimestamp(stat.st_mtime)

            # Check for rapid modifications (suspicious)
            time_diff = (modified_time - created_time).total_seconds()
            if time_diff < 10:
                findings.append({
                    "issue": "rapid_modification",
                    "severity": "medium",
                    "detail": "File created and modified within 10 seconds (suspicious)",
                })

            return {
                "created": created_time.isoformat(),
                "modified": modified_time.isoformat(),
                "size": stat.st_size,
                "findings": findings,
            }
        except Exception as e:
            logger.error(f"Metadata analysis failed: {e}")
            return {"error": str(e), "findings": []}

    @classmethod
    def analyze_content(cls, text: str) -> list[ForensicFinding]:
        """Analyze document content for forgery indicators."""
        findings = []

        # Check for suspicious patterns
        for pattern_name, pattern in cls.SUSPICIOUS_PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                if pattern_name == "inconsistent_dates":
                    # Check if dates are in wrong order
                    if len(matches) > 1:
                        findings.append(
                            ForensicFinding(
                                category="content",
                                severity="medium",
                                finding="Multiple dates found",
                                details=f"Found {len(matches)} date references: {matches[:3]}",
                                recommendation="Verify date chronology in document",
                            )
                        )

                elif pattern_name == "copy_paste_indicators":
                    findings.append(
                        ForensicFinding(
                            category="content",
                            severity="high",
                            finding="Copy-paste indicators detected",
                            details=f"Found: {', '.join(set(matches))}",
                            recommendation="Document may contain copied sections without proper attribution",
                        )
                    )

                elif pattern_name == "placeholder_text":
                    findings.append(
                        ForensicFinding(
                            category="structure",
                            severity="high",
                            finding="Placeholder text found",
                            details=f"Unfilled templates: {', '.join(set(matches[:3]))}",
                            recommendation="Document appears incomplete - placeholders not replaced",
                        )
                    )

                elif pattern_name == "artificial_numbering":
                    findings.append(
                        ForensicFinding(
                            category="structure",
                            severity="low",
                            finding="Unusual article numbering",
                            details="Article numbering format is non-standard",
                            recommendation="Verify numbering against official documents",
                        )
                    )

        # Check for structure issues
        for issue_name, pattern in cls.STRUCTURE_ISSUES.items():
            if not re.search(pattern, text, re.IGNORECASE):
                if issue_name == "missing_jurisdiction":
                    findings.append(
                        ForensicFinding(
                            category="structure",
                            severity="medium",
                            finding="Missing jurisdiction indicator",
                            details="No Kazakhstan/RK/KZ reference found",
                            recommendation="Verify document jurisdiction and origin",
                        )
                    )

        return findings

    @classmethod
    def analyze_structure(cls, text: str) -> list[ForensicFinding]:
        """Analyze document structure for inconsistencies."""
        findings = []

        # Check section consistency
        sections = re.findall(r'^(?:ГЛАВА|РАЗДЕЛ|Статья|ст\.)\s+\d+', text, re.MULTILINE | re.IGNORECASE)
        if sections and len(sections) < 3:
            findings.append(
                ForensicFinding(
                    category="structure",
                    severity="low",
                    finding="Minimal section structure",
                    details=f"Only {len(sections)} major sections detected",
                    recommendation="Verify document is complete and not truncated",
                )
            )

        # Check for definition section
        if not re.search(r'(?:определение|definition|глоссарий|glossary)', text, re.IGNORECASE):
            findings.append(
                ForensicFinding(
                    category="structure",
                    severity="low",
                    finding="No definition section",
                    details="Legal documents typically include term definitions",
                    recommendation="Check if definitions section is missing",
                )
            )

        # Check for amendment history
        has_amendments = re.search(
            r'(?:внесены изменения|amended|изменение|amendment)', text, re.IGNORECASE
        )
        if not has_amendments:
            findings.append(
                ForensicFinding(
                    category="structure",
                    severity="low",
                    finding="No amendment history",
                    details="No record of amendments or modifications",
                    recommendation="Verify if document has been updated or is original version",
                )
            )

        return findings

    @classmethod
    def analyze(cls, text: str, file_path: str = None) -> ForensicReport:
        """Run complete forensic analysis."""
        content_findings = cls.analyze_content(text)
        structure_findings = cls.analyze_structure(text)
        all_findings = content_findings + structure_findings

        # Calculate risk score
        high_severity = len([f for f in all_findings if f.severity == "high"])
        medium_severity = len([f for f in all_findings if f.severity == "medium"])
        low_severity = len([f for f in all_findings if f.severity == "low"])

        risk_score = min(1.0, (high_severity * 0.3 + medium_severity * 0.15 + low_severity * 0.05))

        # Determine risk level
        if risk_score > 0.7:
            risk_level = "critical"
        elif risk_score > 0.5:
            risk_level = "high"
        elif risk_score > 0.3:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Generate summary
        if high_severity > 0:
            summary = f"Document shows {high_severity} critical forensic indicators of potential forgery."
        elif medium_severity > 0:
            summary = f"Document shows {medium_severity} concerning indicators that warrant verification."
        else:
            summary = "Document structure and content appear consistent with legitimate legal documents."

        # Generate recommendations
        recommendations = []
        for finding in all_findings:
            recommendations.append(finding.recommendation)
        if not recommendations:
            recommendations = [
                "Document appears authentic based on forensic analysis",
                "Verify against official sources independently",
                "Consider professional legal review for critical documents",
            ]

        return ForensicReport(
            overall_risk_score=risk_score,
            risk_level=risk_level,
            authenticity_confidence=1.0 - risk_score,
            findings=all_findings,
            summary=summary,
            recommendations=list(set(recommendations))[:5],  # Top 5 unique recommendations
        )


def format_forensic_report(report: ForensicReport) -> dict:
    """Format forensic report for API response."""
    return {
        "risk_assessment": {
            "overall_risk_score": round(report.overall_risk_score, 2),
            "risk_level": report.risk_level,
            "authenticity_confidence": round(report.authenticity_confidence, 2),
        },
        "summary": report.summary,
        "findings": [
            {
                "category": f.category,
                "severity": f.severity,
                "finding": f.finding,
                "details": f.details,
                "recommendation": f.recommendation,
            }
            for f in report.findings
        ],
        "recommendations": report.recommendations,
        "verdict": "⚠️ SUSPICIOUS" if report.risk_level in ["high", "critical"] else "✓ LIKELY AUTHENTIC",
    }
