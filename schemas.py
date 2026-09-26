"""
schemas.py
Pydantic v2 models for ChangeProof's internal data contracts.
Used by synthesizer.py to validate, coerce, and repair findings before output.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


# ── Sub-models ────────────────────────────────────────────────────────────────

class PrimaryLocation(BaseModel):
    file: str = "unknown"
    line: Optional[int] = None


class CodeEvidence(BaseModel):
    modified_symbol: str = "unknown"
    changed_keys: Dict[str, Any] = Field(default_factory=dict)
    violation_direction: Optional[str] = None

    @field_validator("violation_direction")
    @classmethod
    def normalise_direction(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.upper()
            if v not in ("ADDED", "DELETED"):
                return None
        return v


class DocumentEvidence(BaseModel):
    rule_found: bool = False
    source_file: str = "unknown"
    source_line: int = 0
    invariant_text: str = ""
    violation_detected: bool = False
    violation_reason: str = ""


class TestEvidence(BaseModel):
    test_file: str = "unknown"
    test_suite_status: str = "UNKNOWN"
    assertion_covers_rule: bool = False
    unverified_reason: str = ""

    @field_validator("test_suite_status")
    @classmethod
    def normalise_status(cls, v: str) -> str:
        v = v.upper()
        return v if v in ("PASSED", "FAILED", "ERROR", "UNKNOWN", "NOT_AVAILABLE") else "UNKNOWN"


# ── Top-level finding ─────────────────────────────────────────────────────────

VALID_TIERS = {"VIOLATION", "VERIFIED", "UNVERIFIED", "CONTRADICTION", "UNKNOWN"}

class Finding(BaseModel):
    id: str = "RULE-UNKNOWN-000"
    epistemic_tier: str = "UNKNOWN"
    primary_location: PrimaryLocation = Field(default_factory=PrimaryLocation)
    code_evidence: CodeEvidence = Field(default_factory=CodeEvidence)
    document_evidence: DocumentEvidence = Field(default_factory=DocumentEvidence)
    test_evidence: TestEvidence = Field(default_factory=TestEvidence)

    @field_validator("epistemic_tier")
    @classmethod
    def normalise_tier(cls, v: str) -> str:
        v = v.upper()
        return v if v in VALID_TIERS else "UNKNOWN"


# ── Report summary ────────────────────────────────────────────────────────────

class ReportSummary(BaseModel):
    total_findings: int = 0
    violations: int = 0
    verified: int = 0
    unverified: int = 0
    unknown: int = 0

    @model_validator(mode="after")
    def recompute_total(self) -> "ReportSummary":
        """Ensure total_findings is always consistent with the tier counts."""
        computed = self.violations + self.verified + self.unverified + self.unknown
        if self.total_findings != computed and computed > 0:
            self.total_findings = computed
        return self


# ── Full report ───────────────────────────────────────────────────────────────

class ChangeProofReport(BaseModel):
    commit: str = "HEAD"
    summary: ReportSummary = Field(default_factory=ReportSummary)
    findings: List[Finding] = Field(default_factory=list)

    @model_validator(mode="after")
    def sync_summary_from_findings(self) -> "ChangeProofReport":
        """Recompute summary counters from the actual findings list."""
        self.summary.violations  = sum(1 for f in self.findings if f.epistemic_tier == "VIOLATION")
        self.summary.verified    = sum(1 for f in self.findings if f.epistemic_tier == "VERIFIED")
        self.summary.unverified  = sum(1 for f in self.findings if f.epistemic_tier == "UNVERIFIED")
        self.summary.unknown     = sum(1 for f in self.findings if f.epistemic_tier == "UNKNOWN")
        self.summary.total_findings = len(self.findings)
        return self
