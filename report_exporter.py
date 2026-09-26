"""
report_exporter.py
Converts a ChangeProof findings report dict into a GitHub PR-ready
CHANGEPROOF_REPORT.md markdown file.
"""

from pathlib import Path
from datetime import datetime


# Tier → markdown badge text
_TIER_BADGE = {
    "VIOLATION":     "🔴 VIOLATION",
    "VERIFIED":      "🟢 VERIFIED",
    "UNVERIFIED":    "🟡 UNVERIFIED",
    "CONTRADICTION": "⚠️ CONTRADICTION",
    "UNKNOWN":       "⚪ UNKNOWN",
}

_TIER_LABEL = {
    "VIOLATION":     "Critical Architectural Drift",
    "VERIFIED":      "Compliant Change",
    "UNVERIFIED":    "No Test Coverage",
    "CONTRADICTION": "Test Contradicts ADR",
    "UNKNOWN":       "Classification Failed",
}


def export_markdown_report(report: dict, output_path: Path = Path("CHANGEPROOF_REPORT.md")) -> str:
    """
    Renders report dict → markdown string, writes to output_path, returns markdown.
    """
    summary   = report.get("summary", {})
    findings  = report.get("findings", [])
    commit    = report.get("commit", "HEAD")
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    violations = summary.get("violations", 0)
    total      = summary.get("total_findings", 0)

    # ── Header ───────────────────────────────────────────────────────────────
    verdict_line = (
        "## ChangeProof Audit — 🔴 BLOCK: Architectural Violations Detected"
        if violations > 0
        else "## ChangeProof Audit — 🟢 PASS: No Violations Detected"
    )

    lines = [
        verdict_line,
        "",
        f"> **Commit:** `{commit}`  |  **Run:** {timestamp}  |  **Engine:** ChangeProof v1.0",
        "",
        "---",
        "",
        "### Summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Total Findings | **{total}** |",
        f"| 🔴 Violations | **{violations}** |",
        f"| 🟢 Verified | {summary.get('verified', 0)} |",
        f"| 🟡 Unverified | {summary.get('unverified', 0)} |",
        f"| ⚪ Unknown | {summary.get('unknown', 0)} |",
        "",
        "---",
        "",
    ]

    # ── Per-finding detail ────────────────────────────────────────────────────
    if not findings:
        lines.append("_No findings generated — diff produced no ADR-relevant key changes._")
    else:
        lines.append("### Findings")
        lines.append("")

        for i, f in enumerate(findings, start=1):
            tier    = f.get("epistemic_tier", "UNKNOWN")
            fid     = f.get("id", f"RULE-{i:03d}")
            badge   = _TIER_BADGE.get(tier, tier)
            label   = _TIER_LABEL.get(tier, tier)
            loc     = f.get("primary_location", {})
            doc     = f.get("document_evidence", {})
            test    = f.get("test_evidence", {})
            code    = f.get("code_evidence", {})

            file_ref = f"`{loc.get('file', 'unknown')}:{loc.get('line', '?')}`"

            lines += [
                f"#### {badge} — `{fid}`",
                f"**{label}**",
                "",
                f"| Field | Value |",
                f"|-------|-------|",
                f"| Location | {file_ref} |",
                f"| Modified Symbol | `{code.get('modified_symbol', 'N/A')}` |",
                f"| Violation Direction | `{code.get('violation_direction', 'N/A')}` |",
                "",
                "**ADR Invariant Violated**",
                "",
                f"> {doc.get('invariant_text', '_No invariant text_')}",
                "",
                f"- **Source:** `{doc.get('source_file', 'N/A')}` line {doc.get('source_line', '?')}",
                f"- **Reason:** {doc.get('violation_reason', 'N/A')}",
                "",
                "**Test Coverage**",
                "",
                f"| Test File | Suite Status | Asserts Rule? |",
                f"|-----------|-------------|---------------|",
                f"| `{test.get('test_file', 'N/A')}` | {test.get('test_suite_status', 'N/A')} | "
                f"{'✅ Yes' if test.get('assertion_covers_rule') else '❌ No — FALSE GREEN'} |",
                "",
            ]

            if test.get("unverified_reason"):
                lines += [
                    f"> ⚠️ **Gap:** {test['unverified_reason']}",
                    "",
                ]

            lines.append("---")
            lines.append("")

    # ── Remediation checklist ────────────────────────────────────────────────
    violation_findings = [f for f in findings if f.get("epistemic_tier") == "VIOLATION"]
    if violation_findings:
        lines += [
            "### Required Fixes Before Merge",
            "",
        ]
        for f in violation_findings:
            doc  = f.get("document_evidence", {})
            code = f.get("code_evidence", {})
            loc  = f.get("primary_location", {})
            direction = code.get("violation_direction", "")
            key_note = (
                f"Restore the removed field in `{loc.get('file')}`"
                if direction == "DELETED"
                else f"Remove the prohibited field from `{loc.get('file')}`"
            )
            lines += [
                f"- [ ] **{f.get('id')}** — {key_note}",
                f"  - ADR: `{doc.get('source_file')}`",
                f"  - Add a test assertion that explicitly validates this invariant",
                "",
            ]

    # ── Footer ────────────────────────────────────────────────────────────────
    lines += [
        "---",
        "",
        "_Generated by [ChangeProof](https://github.com/ChangeProof) — "
        "Tests tell you code runs. ChangeProof proves code still honors architectural intent._",
    ]

    markdown = "\n".join(lines)
    output_path.write_text(markdown, encoding="utf-8")
    return markdown


if __name__ == "__main__":
    import json
    report = json.loads(Path("findings.json").read_text(encoding="utf-8"))
    export_markdown_report(report)
    print("Report written to CHANGEPROOF_REPORT.md")
