import argparse
import subprocess
import sys
import json
from pathlib import Path
from synthesizer import synthesize_findings
from report_exporter import export_markdown_report


def get_git_diff(commit: str | None = None) -> str:
    """Capture git diff. If a commit hash is supplied, diff that commit against its parent.
    Otherwise fall back to unstaged working-tree changes, then the last commit."""
    try:
        if commit:
            cmd = ["git", "diff", f"{commit}~1", commit]
        else:
            cmd = ["git", "diff", "HEAD"]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        diff = result.stdout.strip()

        # If working-tree is clean and no commit specified, fall back to last commit diff
        if not diff and not commit:
            result = subprocess.run(
                ["git", "diff", "HEAD~1", "HEAD"],
                capture_output=True, text=True, check=True
            )
            diff = result.stdout.strip()
        return diff
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] git diff failed: {e}")
        return ""


def load_adrs() -> dict:
    adr_dir = Path("docs/adr")
    adrs = {}
    if adr_dir.exists():
        for file in adr_dir.glob("*.md"):
            adrs[file.name] = file.read_text(encoding="utf-8")
    return adrs


def load_tests() -> dict:
    test_dir = Path("tests")
    tests = {}
    if test_dir.exists():
        for file in test_dir.glob("test_*.py"):
            tests[file.name] = file.read_text(encoding="utf-8")
    return tests


def display_findings(report: dict):
    summary = report.get("summary", {})

    print("\n" + "=" * 65)
    print("           CHANGEPROOF INVARIANT VERIFICATION REPORT            ")
    print("=" * 65)
    print(f" Total Findings : {summary.get('total_findings', 0)}")
    print(f" [!!] Violations : {summary.get('violations', 0)}  [CRITICAL DRIFT DETECTED]")
    print(f" [OK] Verified   : {summary.get('verified', 0)}")
    print(f" [??] Unverified : {summary.get('unverified', 0)}")
    print(f" [--] Unknown    : {summary.get('unknown', 0)}")
    print("-" * 65)

    for finding in report.get("findings", []):
        loc = finding.get("primary_location", {})
        doc = finding.get("document_evidence", {})
        test = finding.get("test_evidence", {})
        tier = finding.get("epistemic_tier")
        icon = "[!!]" if tier == "VIOLATION" else "[OK]"

        print(f"\n{icon} [{tier}] ID: {finding.get('id')}")
        print(f"   Target Location : {loc.get('file')}:{loc.get('line')}")
        print(f"   Invariant Rule  : \"{doc.get('invariant_text')}\"")
        print(f"   Rule Source     : {doc.get('source_file')}:{doc.get('source_line')}")
        print(f"   Violation Detail: {doc.get('violation_reason')}")
        print(f"   Test Coverage   : {test.get('unverified_reason')}")
    print("\n" + "=" * 65)


def main():
    parser = argparse.ArgumentParser(
        description="ChangeProof — Autonomous Architectural Invariant Auditor"
    )
    parser.add_argument(
        "--diff",
        metavar="COMMIT",
        default=None,
        help="Commit hash to audit (diffs COMMIT~1..COMMIT). Omit to audit working-tree changes.",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip writing CHANGEPROOF_REPORT.md",
    )
    args = parser.parse_args()

    print("=" * 65)
    print(" CHANGEPROOF: Autonomous Architectural Invariant Auditor ")
    print("=" * 65)

    diff = get_git_diff(commit=args.diff)
    if not diff:
        print("No changes detected in Git workspace.")
        sys.exit(0)

    print(f"[+] Captured Git Diff ({len(diff.splitlines())} lines modified)"
          + (f" for commit {args.diff}" if args.diff else ""))

    adrs = load_adrs()
    print(f"[+] Loaded {len(adrs)} Architecture Decision Records (ADRs)")

    tests = load_tests()
    print(f"[+] Loaded {len(tests)} Test Suite Files")

    context = {"diff": diff, "adrs": adrs, "tests": tests}
    context_path = Path("audit_context.json")
    context_path.write_text(json.dumps(context, indent=2), encoding="utf-8")
    print(f"[+] Written audit context to {context_path.name}")

    print("[*] Running AST assertion analysis and semantic invariant synthesis...")
    report = synthesize_findings(context_path)

    display_findings(report)

    if not args.no_report:
        export_markdown_report(report, Path("CHANGEPROOF_REPORT.md"))
        print("[+] GitHub PR report written to CHANGEPROOF_REPORT.md")


if __name__ == "__main__":
    main()
