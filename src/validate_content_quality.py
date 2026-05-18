import re
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

        # A real generated client folder should have at least one of these.
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


def validate_file(path: Path) -> List[str]:
    if not path.exists():
        return [f"Missing expected content file: {path}"]

    text = path.read_text(encoding="utf-8", errors="replace")
    findings = scan_text(text)

    errors = []

    for category, pattern in findings:
        errors.append(
            f"{path}: matched banned content category '{category}' with pattern '{pattern}'"
        )

    return errors


def main() -> None:
    week_dir = get_latest_week_dir()
    client_dirs = discover_client_dirs(week_dir)

    errors: List[str] = []

    for client_dir in client_dirs:
        for filename in FILES_TO_SCAN:
            errors.extend(validate_file(client_dir / filename))

    if errors:
        print("CONTENT QUALITY CHECK FAILED")
        print(f"Week: {week_dir.name}")
        print(f"Client folders checked: {len(client_dirs)}")
        print(f"Errors found: {len(errors)}")

        for error in errors:
            print(f"- {error}")

        raise SystemExit(1)

    print("CONTENT QUALITY CHECK PASSED")
    print(f"Week: {week_dir.name}")
    print(f"Client folders checked: {len(client_dirs)}")
    print(f"Files checked per client: {len(FILES_TO_SCAN)}")


if __name__ == "__main__":
    main()
