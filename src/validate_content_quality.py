import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "output"


BANNED_PATTERNS: Dict[str, List[str]] = {
    "fake_or_risky_pay_claims": [
        r"\bguaranteed\s+pay\b",
        r"\btop\s+pay\b",
        r"\btop[-\s]?paying\b",
        r"\bbest\s+pay\b",
        r"\bbest[-\s]?paying\b",
        r"\bunbeatable\s+pay\b",
        r"\bhighest\s+pay\b",
        r"\bguaranteed\s+income\b",
    ],
    "fake_or_risky_miles_claims": [
        r"\bguaranteed\s+miles\b",
        r"\bguaranteed\s+weekly\s+miles\b",
        r"\bguaranteed\s+loads\b",
        r"\bnever\s+sit\b",
        r"\bno\s+downtime\b",
    ],
    "fake_or_risky_hometime_claims": [
        r"\bguaranteed\s+home\s+time\b",
        r"\bguaranteed\s+hometime\b",
        r"\bhome\s+every\s+weekend\b",
        r"\bevery\s+weekend\s+home\b",
    ],
    "fake_or_risky_bonus_claims": [
        r"\bsign[-\s]?on\s+bonus\b",
        r"\bsignup\s+bonus\b",
        r"\bbonus\s+guaranteed\b",
        r"\bguaranteed\s+bonus\b",
    ],
    "overhyped_marketing_claims": [
        r"\bbest\s+company\b",
        r"\bbest\s+carrier\b",
        r"\bunbeatable\b",
        r"\bno\s+one\s+beats\b",
        r"\bperfect\s+job\b",
        r"\bdream\s+job\b",
    ],
}


FILES_TO_SCAN = [
    "recruiting_posts.md",
    "social_posts.md",
    "safety_reminders.md",
    "company_update.md",
    "freight_digest.md",
    "full_pack.md",
]


SKIP_DIR_NAMES = {
    "_packages",
    "__pycache__",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_latest_week_dir() -> Path:
    if not OUTPUT_DIR.exists():
        raise RuntimeError(f"Missing output directory: {OUTPUT_DIR}")

    week_dirs = sorted(
        [
            path
            for path in OUTPUT_DIR.iterdir()
            if path.is_dir() and re.match(r"^\d{4}-W\d{2}$", path.name)
        ]
    )

    if not week_dirs:
        raise RuntimeError(f"No week output directories found in: {OUTPUT_DIR}")

    return week_dirs[-1]


def discover_client_dirs(week_dir: Path) -> List[Path]:
    client_dirs = []

    for path in sorted(week_dir.iterdir()):
        if not path.is_dir():
            continue

        if path.name in SKIP_DIR_NAMES:
            continue

        if (path / "meta.json").exists() or (path / "full_pack.md").exists():
            client_dirs.append(path)

    if not client_dirs:
        raise RuntimeError(f"No generated client folders found in: {week_dir}")

    return client_dirs


def scan_text(text: str) -> List[Tuple[str, str]]:
    findings: List[Tuple[str, str]] = []

    for category, patterns in BANNED_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                findings.append((category, pattern))

    return findings


def validate_file(path: Path) -> Dict:
    record = {
        "file": str(path.relative_to(ROOT_DIR)),
        "exists": path.exists(),
        "passed": True,
        "matches": [],
    }

    if not path.exists():
        record["passed"] = False
        record["matches"].append(
            {
                "category": "missing_file",
                "pattern": None,
                "message": "Missing expected content file.",
            }
        )
        return record

    text = path.read_text(encoding="utf-8", errors="replace")
    findings = scan_text(text)

    if findings:
        record["passed"] = False

    for category, pattern in findings:
        record["matches"].append(
            {
                "category": category,
                "pattern": pattern,
                "message": f"Matched banned content category '{category}' with pattern '{pattern}'.",
            }
        )

    return record


def write_report(week_dir: Path, report: Dict) -> Path:
    report_path = week_dir / "content_quality_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


def main() -> None:
    week_dir = get_latest_week_dir()
    client_dirs = discover_client_dirs(week_dir)

    report = {
        "week": week_dir.name,
        "checked_at": now_iso(),
        "status": "passed",
        "client_count": len(client_dirs),
        "files_checked_per_client": len(FILES_TO_SCAN),
        "banned_pattern_categories": list(BANNED_PATTERNS.keys()),
        "clients": [],
        "error_count": 0,
    }

    error_count = 0

    for client_dir in client_dirs:
        client_record = {
            "client_folder": client_dir.name,
            "status": "passed",
            "files": [],
        }

        for filename in FILES_TO_SCAN:
            file_record = validate_file(client_dir / filename)
            client_record["files"].append(file_record)

            if not file_record["passed"]:
                client_record["status"] = "failed"
                error_count += len(file_record["matches"])

        report["clients"].append(client_record)

    report["error_count"] = error_count

    if error_count:
        report["status"] = "failed"

    report_path = write_report(week_dir, report)

    if error_count:
        print("CONTENT QUALITY CHECK FAILED")
        print(f"Week: {week_dir.name}")
        print(f"Client folders checked: {len(client_dirs)}")
        print(f"Files checked per client: {len(FILES_TO_SCAN)}")
        print(f"Errors found: {error_count}")
        print(f"Report written: {report_path}")

        for client_record in report["clients"]:
            for file_record in client_record["files"]:
                if file_record["passed"]:
                    continue

                for match in file_record["matches"]:
                    print(
                        f"- {file_record['file']}: "
                        f"{match['category']} | {match['pattern']} | {match['message']}"
                    )

        raise SystemExit(1)

    print("CONTENT QUALITY CHECK PASSED")
    print(f"Week: {week_dir.name}")
    print(f"Client folders checked: {len(client_dirs)}")
    print(f"Files checked per client: {len(FILES_TO_SCAN)}")
    print(f"Report written: {report_path}")


if __name__ == "__main__":
    main()
