import csv
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Iterable


SLACK_PATTERN = re.compile(r"^- \*\*(?P<ts>[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2})\*\* \*(?P<actor>[^*]+)\*: (?P<content>.*)$")


# --- Slack helpers ---------------------------------------------------------

def parse_slack_file(path: Path) -> Iterable[Dict[str, Any]]:
    """Yield timeline rows from a Slack markdown file."""
    channel = path.stem  # filename minus .md
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            m = SLACK_PATTERN.match(line)
            if not m:
                continue  # skip headers or non-message lines
            ts_str = m.group("ts")
            # Slack export timestamps are local; assume US/Eastern for now
            timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
            yield {
                "timestamp": timestamp.isoformat(),
                "source": "slack",
                "actor": m.group("actor"),
                "channel_or_subject": channel,
                "event_type": "message",
                "content": m.group("content"),
            }


# --- Email helpers ---------------------------------------------------------

def parse_email_file(path: Path) -> Iterable[Dict[str, Any]]:
    """Yield a single timeline row for an archived email markdown file."""
    with path.open(encoding="utf-8") as fh:
        headers_done = False
        headers = {}
        body_lines: List[str] = []
        for line in fh:
            if not headers_done:
                if line.strip() == "":
                    headers_done = True
                    continue
                if ":" in line:
                    key, val = line.split(":", 1)
                    headers[key.strip().lower()] = val.strip()
            else:
                body_lines.append(line.rstrip("\n"))

    date_str = headers.get("date")
    if date_str:
        try:
            timestamp = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
        except ValueError:
            # fallback: try without timezone
            try:
                timestamp = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S")
            except ValueError:
                timestamp = None
    else:
        # derive from filename prefix YYYYMMDD
        try:
            ts_prefix = path.name[:8]
            timestamp = datetime.strptime(ts_prefix, "%Y%m%d")
        except ValueError:
            timestamp = None

    yield {
        "timestamp": timestamp.isoformat() if timestamp else "",
        "source": "email",
        "actor": headers.get("from", ""),
        "channel_or_subject": headers.get("subject", path.stem),
        "event_type": "email",
        "content": "\n".join(body_lines)[:5000],  # clip very long bodies
    }


# --- Orchestration ---------------------------------------------------------

def walk_files(root: Path, glob: str) -> List[Path]:
    return sorted(root.rglob(glob))


def build_timeline(slack_dir: Path, email_dir: Path, output_csv: Path):
    rows: List[Dict[str, Any]] = []
    print(f"Parsing Slack files in {slack_dir}…")
    for f in walk_files(slack_dir, "*.md"):
        rows.extend(parse_slack_file(f))

    print(f"Parsing email files in {email_dir}…")
    for f in walk_files(email_dir, "*.md"):
        rows.extend(parse_email_file(f))

    print(f"Writing {len(rows)} rows → {output_csv}")
    with output_csv.open("w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["timestamp", "source", "actor", "channel_or_subject", "event_type", "content"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for r in sorted(rows, key=lambda x: x["timestamp"] or ""):
            writer.writerow(r)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build unified timeline CSV from Slack & Gmail markdown exports.")
    parser.add_argument("--slack_dir", type=Path, default=Path("slack/markdown_exports"), help="Path to Slack markdown directory")
    parser.add_argument("--email_dir", type=Path, default=Path("mail/archive"), help="Path to Gmail archive directory")
    parser.add_argument("--output", type=Path, default=Path("brain/timeline.csv"), help="Output CSV path (default: brain/timeline.csv)")
    args = parser.parse_args()

    # Ensure destination directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)
    build_timeline(args.slack_dir, args.email_dir, args.output) 