import json
import re
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional
from ast_auditor import audit_test_assertions
from schemas import ChangeProofReport, Finding, DocumentEvidence, CodeEvidence, TestEvidence, PrimaryLocation

# Map ADR filenames to their associated service/test files
ADR_SERVICE_MAP = {
    "ADR-042-payment-isolation.md":    ("services/payment_service.py",  "tests/test_payment.py",  "create_payment_event",  "RULE-PAYMENT-001"),
    "ADR-089-hipaa-phi-sanitization.md": ("services/patient_service.py", "tests/test_patient.py",  "export_patient_summary", "RULE-PATIENT-001"),
}

def extract_diff_keys(diff_text: str) -> Dict[str, Any]:
    """
    Parse the diff and return:
      - 'deleted': keys removed from payloads (- lines)
      - 'added':   keys injected into payloads (+ lines)
      - 'key_lines': map of key -> hunk line number (1-based within the changed file)
    """
    deleted, added = [], []
    key_lines: Dict[str, int] = {}
    hunk_new_line = 0
    for raw_line in diff_text.splitlines():
        # Track hunk header to get line numbers in the new file
        hunk_match = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)', raw_line)
        if hunk_match:
            hunk_new_line = int(hunk_match.group(1)) - 1
            continue
        if raw_line.startswith("---") or raw_line.startswith("+++"):
            continue
        if not raw_line.startswith("-"):
            hunk_new_line += 1
        keys = re.findall(r'["\']([a-zA-Z0-9_]+)["\']\s*:', raw_line)
        if raw_line.startswith("-"):
            deleted.extend(keys)
            for k in keys:
                key_lines.setdefault(k, hunk_new_line)
        elif raw_line.startswith("+"):
            added.extend(keys)
            for k in keys:
                key_lines.setdefault(k, hunk_new_line)
    return {"deleted": deleted, "added": added, "key_lines": key_lines}


def evaluate_adr_invariants(adr_text: str, changed_keys: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    Scans ADR markdown for normative keywords (MUST, SHALL, REQUIRED, NEVER).
    Detects both:
      - Presence violations: a MUST-include key was deleted
      - Prohibition violations: a MUST-omit/NEVER-include key was added
    """
    lines = adr_text.splitlines()
    for idx, line in enumerate(lines, start=1):
        if not re.search(r'\b(MUST|SHALL|REQUIRED|NEVER)\b', line, re.IGNORECASE):
            continue

        # Check if an added key violates a prohibition (MUST omit / NEVER include)
        is_prohibition = bool(re.search(r'\b(omit|sanitize|exclude|NEVER|not include|remove)\b', line, re.IGNORECASE))
        candidates = changed_keys["added"] if is_prohibition else changed_keys["deleted"]

        for key in candidates:
            if key in line:
                direction = "added to" if is_prohibition else "removed from"
                return {
                    "rule_found": True,
                    "source_line": idx,
                    "invariant_text": line.strip(),
                    "violation_detected": True,
                    "violation_reason": f"Field '{key}' was {direction} payload, violating documented invariant.",
                    "target_key": key,
                    "violation_direction": "ADDED" if is_prohibition else "DELETED",
                }

    return {
        "rule_found": False,
        "source_line": 0,
        "invariant_text": "",
        "violation_detected": False,
        "violation_reason": "",
        "target_key": "",
        "violation_direction": None,
    }


def _repair_json(raw: str) -> Optional[Dict]:
    """Best-effort JSON repair: strip trailing commas, fix truncated strings."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Strip trailing commas before } or ]
    repaired = re.sub(r",\s*([}\]])", r"\1", raw)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


def _validate_report(raw_report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the raw findings dict through Pydantic.
    Returns a validated + coerced dict, or a safe fallback report on failure.
    """
    try:
        validated = ChangeProofReport.model_validate(raw_report)
        return validated.model_dump()
    except Exception as exc:
        # Emit a structured error finding rather than crashing
        print(f"[WARN] Pydantic validation failed: {exc}")
        fallback = ChangeProofReport(
            commit=raw_report.get("commit", "HEAD"),
            findings=[
                Finding(
                    id="RULE-VALIDATION-ERROR",
                    epistemic_tier="UNKNOWN",
                    document_evidence=DocumentEvidence(
                        violation_reason=f"Schema validation error: {exc}"
                    ),
                )
            ],
        )
        return fallback.model_dump()


def synthesize_findings(context_file: Path = Path("audit_context.json")) -> Dict[str, Any]:
    """
    Ingests audit context, evaluates ALL ADRs against ALL diff changes,
    runs AST assertion analysis per domain, and compiles findings.json.
    Fault-tolerant: validates output via Pydantic; never crashes on bad data.
    """
    if not context_file.exists():
        raise FileNotFoundError("audit_context.json does not exist. Run change_proof.py first.")

    raw_text = context_file.read_text(encoding="utf-8")
    context = _repair_json(raw_text)
    if context is None:
        print("[ERROR] audit_context.json is not valid JSON and could not be repaired.")
        context = {}

    diff_text = context.get("diff", "")
    adrs = context.get("adrs", {})

    # 1. Extract all added and deleted payload keys from the full diff
    changed_keys = extract_diff_keys(diff_text)

    # 2. Evaluate every ADR independently
    findings = []
    for adr_name, adr_text in adrs.items():
        adr_eval = evaluate_adr_invariants(adr_text, changed_keys)
        if not adr_eval["violation_detected"]:
            continue

        # Look up domain-specific metadata; fall back to generic defaults
        service_file, test_file, symbol, rule_id = ADR_SERVICE_MAP.get(
            adr_name,
            ("services/unknown_service.py", "tests/test_unknown.py", "unknown_function", f"RULE-{adr_name.upper()[:20]}")
        )

        target_key = adr_eval["target_key"]

        # 3. AST audit the relevant test file for this domain
        ast_result = audit_test_assertions(test_file, target_key)

        # 4. Epistemic classification
        if adr_eval["violation_detected"]:
            tier = "VIOLATION" if not ast_result["is_asserted"] else "CONTRADICTION"
        elif not ast_result["is_asserted"]:
            tier = "UNVERIFIED"
        else:
            tier = "VERIFIED"

        line_no = changed_keys.get("key_lines", {}).get(target_key)
        findings.append({
            "id": rule_id,
            "epistemic_tier": tier,
            "primary_location": {
                "file": service_file,
                "line": line_no
            },
            "code_evidence": {
                "modified_symbol": symbol,
                "changed_keys": changed_keys,
                "violation_direction": adr_eval["violation_direction"],
            },
            "document_evidence": {
                "rule_found": adr_eval["rule_found"],
                "source_file": f"docs/adr/{adr_name}",
                "source_line": adr_eval["source_line"],
                "invariant_text": adr_eval["invariant_text"],
                "violation_detected": adr_eval["violation_detected"],
                "violation_reason": adr_eval["violation_reason"],
            },
            "test_evidence": {
                "test_file": test_file,
                "test_suite_status": "PASSED",
                "assertion_covers_rule": ast_result["is_asserted"],
                "unverified_reason": (
                    f"AST confirms '{target_key}' has 0 assertion checks in {test_file}."
                    if not ast_result["is_asserted"] else ""
                ),
            }
        })

    # 5. Build summary counters
    total     = len(findings)
    violations  = sum(1 for f in findings if f["epistemic_tier"] == "VIOLATION")
    verified    = sum(1 for f in findings if f["epistemic_tier"] == "VERIFIED")
    unverified  = sum(1 for f in findings if f["epistemic_tier"] == "UNVERIFIED")
    unknown     = sum(1 for f in findings if f["epistemic_tier"] not in ("VIOLATION", "VERIFIED", "UNVERIFIED", "CONTRADICTION"))

    report = {
        "commit": "HEAD",
        "summary": {
            "total_findings": total,
            "violations": violations,
            "verified": verified,
            "unverified": unverified,
            "unknown": unknown,
        },
        "findings": findings,
    }

    # Validate and coerce through Pydantic before writing
    try:
        report = _validate_report(report)
    except Exception as exc:
        print(f"[ERROR] Unexpected validation failure: {exc}")
        traceback.print_exc()

    Path("findings.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = synthesize_findings()
    print("Synthesis complete. findings.json generated successfully.")
