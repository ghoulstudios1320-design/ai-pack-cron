import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "output"


EXPECTED_FILES = [
    "full_pack.pdf",
    "full_pack.md",
    "recruiting_posts.md",
    "social_posts.md",
    "safety_reminders.md",
    "company_update.md",
    "freight_digest.md",
    "meta.json",
]


def find_week_dir() -> Path:
    week_key = os.getenv("WEEK_KEY", "").strip()

    if week_key:
        week_dir = OUTPUT_DIR / week_key
        if not week_dir.exists():
            raise RuntimeError(f"WEEK_KEY was set but output folder does not exist: {week_dir}")
        return week_dir

    if not OUTPUT_DIR.exists():
        raise RuntimeError(f"Output directory does not exist: {OUTPUT_DIR}")

    week_dirs = [p for p in OUTPUT_DIR.iterdir() if p.is_dir()]

    if not week_dirs:
        raise RuntimeError(f"No week folders found in: {OUTPUT_DIR}")

    return sorted(week_dirs, key=lambda p: p.name)[-1]


def read_meta(client_dir: Path) -> Dict[str, str]:
    meta_path = client_dir / "meta.json"

    if not meta_path.exists():
        return {}

    with meta_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def zip_client_folder(client_dir: Path, packages_dir: Path, week_key: str) -> Dict[str, str]:
    meta = read_meta(client_dir)

    client_id = meta.get("client_id") or client_dir.name
    company_name = meta.get("company_name") or client_id

    zip_name = f"{client_id}_{week_key}_pack.zip"
    zip_path = packages_dir / zip_name

    included_files: List[Path] = []

    for file_name in EXPECTED_FILES:
        file_path = client_dir / file_name

        if file_path.exists() and file_path.is_file():
            included_files.append(file_path)

    if not included_files:
        raise RuntimeError(f"No expected files found for client folder: {client_dir}")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in included_files:
            zf.write(file_path, arcname=file_path.name)

    print(f"Packaged {company_name}: {zip_path}")

    return {
        "client_id": client_id,
        "company_name": company_name,
        "package_zip": f"_packages/{zip_name}",
        "client_folder": client_dir.name,
        "pdf": f"{client_dir.name}/full_pack.pdf",
        "markdown": f"{client_dir.name}/full_pack.md",
        "meta": f"{client_dir.name}/meta.json",
    }


def build_run_summary(
    week_dir: Path,
    packages_dir: Path,
    package_records: List[Dict[str, str]],
) -> None:
    week_key = week_dir.name
    generated_at = datetime.now(timezone.utc).isoformat()

    lines = [
        f"# Trucking Pack Run Summary - {week_key}",
        "",
        f"Generated at UTC: {generated_at}",
        "",
        "## Client Packages",
        "",
    ]

    for record in sorted(package_records, key=lambda r: r["client_id"]):
        lines.append(
            f"- `{record['package_zip']}` ({record['company_name']})"
        )

    lines.extend(
        [
            "",
            "## Expected package contents",
            "",
        ]
    )

    for file_name in EXPECTED_FILES:
        lines.append(f"- `{file_name}`")

    summary_path = packages_dir / "run_summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote run summary: {summary_path}")


def build_master_index(
    week_dir: Path,
    package_records: List[Dict[str, str]],
) -> None:
    week_key = week_dir.name

    master_index = {
        "week": week_key,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "client_count": len(package_records),
        "clients": sorted(package_records, key=lambda r: r["client_id"]),
    }

    index_path = week_dir / "master_index.json"

    index_path.write_text(
        json.dumps(master_index, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote master index: {index_path}")


def main() -> None:
    week_dir = find_week_dir()
    week_key = week_dir.name

    packages_dir = week_dir / "_packages"
    packages_dir.mkdir(parents=True, exist_ok=True)

    client_dirs = [
        p for p in week_dir.iterdir()
        if p.is_dir() and not p.name.startswith("_")
    ]

    if not client_dirs:
        raise RuntimeError(f"No client output folders found in: {week_dir}")

    package_records = []

    for client_dir in sorted(client_dirs, key=lambda p: p.name):
        package_records.append(
            zip_client_folder(client_dir, packages_dir, week_key)
        )

    build_run_summary(
        week_dir,
        packages_dir,
        package_records,
    )

    build_master_index(
        week_dir,
        package_records,
    )

    print("All client packages created successfully.")


if __name__ == "__main__":
    main()
