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


REQUIRED_OPERATIONAL_MEMORY_CATEGORIES = [
    "appointment_pressure",
    "detention",
    "freight_volume",
    "weather_disruption",
    "equipment_issues",
    "customer_pressure",
    "lane_activity",
]


REQUIRED_OPERATIONAL_MEMORY_FIELDS = [
    "status",
    "previous_status",
    "trend_delta",
    "weeks_observed",
    "summary",
    "evidence",
    "severity",
]


ALLOWED_TREND_DELTAS = {
    "insufficient_history",
    "new",
    "resolved",
    "worsening",
    "improving",
    "persistent",
    "stable",
    "changed",
}


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


def validate_operational_memory(path: Path) -> Dict:
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
                "category": "missing_operational_memory",
                "pattern": None,
                "message": "Missing operational_memory.json.",
            }
        )
        return record

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        record["passed"] = False
        record["matches"].append(
            {
                "category": "invalid_operational_memory_json",
                "pattern": None,
                "message": f"operational_memory.json is invalid JSON: {exc}",
            }
        )
        return record

    memory_version = data.get("memory_version")
    if not isinstance(memory_version, str) or not memory_version.strip():
        record["passed"] = False
        record["matches"].append(
            {
                "category": "invalid_operational_memory_version",
                "pattern": None,
                "message": "operational_memory.json memory_version must be a non-empty string.",
            }
        )

    categories = data.get("categories")

    if not isinstance(categories, dict):
        record["passed"] = False
        record["matches"].append(
            {
                "category": "invalid_operational_memory_structure",
                "pattern": None,
                "message": "operational_memory.json categories must be an object.",
            }
        )
        return record

    for category in REQUIRED_OPERATIONAL_MEMORY_CATEGORIES:
        if category not in categories:
            record["passed"] = False
            record["matches"].append(
                {
                    "category": "missing_operational_memory_category",
                    "pattern": None,
                    "message": f"Missing operational memory category: {category}",
                }
            )
            continue

        entry = categories[category]

        if not isinstance(entry, dict):
            record["passed"] = False
            record["matches"].append(
                {
                    "category": "invalid_operational_memory_category",
                    "pattern": None,
                    "message": f"{category} must be an object.",
                }
            )
            continue

        for field in REQUIRED_OPERATIONAL_MEMORY_FIELDS:
            if field not in entry:
                record["passed"] = False
                record["matches"].append(
                    {
                        "category": "missing_operational_memory_field",
                        "pattern": None,
                        "message": f"{category} missing field: {field}",
                    }
                )

        status = entry.get("status")
        if not isinstance(status, str) or not status.strip():
            record["passed"] = False
            record["matches"].append(
                {
                    "category": "invalid_operational_memory_status",
                    "pattern": None,
                    "message": f"{category} status must be a non-empty string.",
                }
            )

        previous_status = entry.get("previous_status")
        if not isinstance(previous_status, str) or not previous_status.strip():
            record["passed"] = False
            record["matches"].append(
                {
                    "category": "invalid_operational_memory_previous_status",
                    "pattern": None,
                    "message": f"{category} previous_status must be a non-empty string.",
                }
            )

        trend_delta = entry.get("trend_delta")
        if not isinstance(trend_delta, str) or not trend_delta.strip():
            record["passed"] = False
            record["matches"].append(
                {
                    "category": "invalid_operational_memory_trend_delta",
                    "pattern": None,
                    "message": f"{category} trend_delta must be a non-empty string.",
                }
            )
        elif trend_delta not in ALLOWED_TREND_DELTAS:
            record["passed"] = False
            record["matches"].append(
                {
                    "category": "unknown_operational_memory_trend_delta",
                    "pattern": None,
                    "message": (
                        f"{category} trend_delta '{trend_delta}' is not in the allowed set: "
                        f"{sorted(ALLOWED_TREND_DELTAS)}"
                    ),
                }
            )

        weeks_observed = entry.get("weeks_observed")
        if not isinstance(weeks_observed, int) or weeks_observed < 0:
            record["passed"] = False
            record["matches"].append(
                {
                    "category": "invalid_operational_memory_weeks_observed",
                    "pattern": None,
                    "message": f"{category} weeks_observed must be an integer greater than or equal to 0.",
                }
            )

        summary = entry.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            record["passed"] = False
            record["matches"].append(
                {
                    "category": "invalid_operational_memory_summary",
                    "pattern": None,
                    "message": f"{category} summary must be a non-empty string.",
                }
            )

        evidence = entry.get("evidence")
        if not isinstance(evidence, list):
            record["passed"] = False
            record["matches"].append(
                {
                    "category": "invalid_operational_memory_evidence",
                    "pattern": None,
                    "message": f"{category} evidence must be a list.",
                }
            )
        else:
            for index, item in enumerate(evidence):
                if not isinstance(item, str):
                    record["passed"] = False
                    record["matches"].append(
                        {
                            "category": "invalid_operational_memory_evidence_item",
                            "pattern": None,
                            "message": f"{category} evidence item {index} must be a string.",
                        }
                    )

        severity = entry.get("severity")
        if not isinstance(severity, int) or severity < 1 or severity > 5:
            record["passed"] = False
            record["matches"].append(
                {
                    "category": "invalid_operational_memory_severity",
                    "pattern": None,
                    "message": f"{category} severity must be an integer from 1 to 5.",
                }
            )

    return record


def validate_client_intelligence_summary(path: Path) -> Dict:
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
                "category": "missing_client_intelligence_summary",
                "pattern": None,
                "message": "Missing client_intelligence_summary.md.",
            }
        )
        return record

    text = path.read_text(encoding="utf-8", errors="replace").strip()

    if not text:
        record["passed"] = False
        record["matches"].append(
            {
                "category": "empty_client_intelligence_summary",
                "pattern": None,
                "message": "client_intelligence_summary.md is empty.",
            }
        )
        return record

    required_headings = [
        "# Weekly Client Intelligence Summary",
        "## Executive Readout",
        "## Trend Breakdown",
        "## Recommended Focus",
        "## Raw Category Snapshot",
    ]

    for heading in required_headings:
        if heading not in text:
            record["passed"] = False
            record["matches"].append(
                {
                    "category": "missing_client_intelligence_summary_heading",
                    "pattern": heading,
                    "message": f"client_intelligence_summary.md missing heading: {heading}",
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
        "operational_memory_checked_per_client": 1,
        "client_intelligence_summary_checked_per_client": 1,
        "banned_pattern_categories": list(BANNED_PATTERNS.keys()),
        "required_operational_memory_categories": REQUIRED_OPERATIONAL_MEMORY_CATEGORIES,
        "required_operational_memory_fields": REQUIRED_OPERATIONAL_MEMORY_FIELDS,
        "allowed_trend_deltas": sorted(ALLOWED_TREND_DELTAS),
        "clients": [],
        "error_count": 0,
    }

    error_count = 0

    for client_dir in client_dirs:
        client_record = {
            "client_folder": client_dir.name,
            "status": "passed",
            "files": [],
            "operational_memory": None,
            "client_intelligence_summary": None,
        }

        for filename in FILES_TO_SCAN:
            file_record = validate_file(client_dir / filename)
            client_record["files"].append(file_record)

            if not file_record["passed"]:
                client_record["status"] = "failed"
                error_count += len(file_record["matches"])

        memory_record = validate_operational_memory(
            client_dir / "operational_memory.json"
        )
        client_record["operational_memory"] = memory_record

        if not memory_record["passed"]:
            client_record["status"] = "failed"
            error_count += len(memory_record["matches"])

        summary_record = validate_client_intelligence_summary(
            client_dir / "client_intelligence_summary.md"
        )
        client_record["client_intelligence_summary"] = summary_record

        if not summary_record["passed"]:
            client_record["status"] = "failed"
            error_count += len(summary_record["matches"])

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
        print("Operational memory checked per client: 1")
        print("Client intelligence summary checked per client: 1")
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

            memory_record = client_record.get("operational_memory")

            if memory_record and not memory_record["passed"]:
                for match in memory_record["matches"]:
                    print(
                        f"- {memory_record['file']}: "
                        f"{match['category']} | {match['pattern']} | {match['message']}"
                    )

            summary_record = client_record.get("client_intelligence_summary")

            if summary_record and not summary_record["passed"]:
                for match in summary_record["matches"]:
                    print(
                        f"- {summary_record['file']}: "
                        f"{match['category']} | {match['pattern']} | {match['message']}"
                    )

        raise SystemExit(1)

    print("CONTENT QUALITY CHECK PASSED")
    print(f"Week: {week_dir.name}")
    print(f"Client folders checked: {len(client_dirs)}")
    print(f"Files checked per client: {len(FILES_TO_SCAN)}")
    print("Operational memory checked per client: 1")
    print("Client intelligence summary checked per client: 1")
    print(f"Report written: {report_path}")


if __name__ == "__main__":
    main()
