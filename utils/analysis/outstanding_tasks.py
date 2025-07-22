import csv
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

ASSIGNEE_PATTERNS = [
    re.compile(r"\bJourdan\b", re.IGNORECASE),
    re.compile(r"<@U0913R7KB7E>"),  # Slack user ID for Jourdan (from sample)
]

REQUEST_PATTERNS = [
    re.compile(r"\b(can you|please|need|could you|would you|follow up|ping|assign|todo|to do)\b", re.IGNORECASE),
]

COMPLETION_PATTERNS = [
    re.compile(r"\b(done|completed|finished|fixed|pushed|sent|delivered)\b", re.IGNORECASE),
]


def load_timeline(csv_path: Path) -> List[Dict[str, str]]:
    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def is_within_days(ts_str: str, days: int = 7) -> bool:
    if not ts_str:
        return False
    try:
        ts = datetime.fromisoformat(ts_str)
    except ValueError:
        return False
    return ts >= datetime.now() - timedelta(days=days)


def find_outstanding(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    pending = []
    completed = defaultdict(list)  # content excerpt -> timestamp

    # First pass: gather completions by Jourdan
    for row in rows:
        if row["actor"].lower().startswith("jourdan") and any(p.search(row["content"]) for p in COMPLETION_PATTERNS):
            completed[row["content"][:100]].append(row["timestamp"])

    # Second pass: find requests involving Jourdan
    for row in rows:
        if not is_within_days(row["timestamp"], 7):
            continue
        if any(p.search(row["content"]) for p in ASSIGNEE_PATTERNS) and any(q.search(row["content"]) for q in REQUEST_PATTERNS):
            excerpt = row["content"][:200]
            # crude check for completion: see if any completion from Jourdan after this timestamp
            ts_request = datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else None
            resolved = False
            if ts_request:
                for comp_list in completed.values():
                    for comp_ts_str in comp_list:
                        try:
                            comp_ts = datetime.fromisoformat(comp_ts_str)
                            if comp_ts > ts_request:
                                resolved = True
                                break
                        except ValueError:
                            continue
                    if resolved:
                        break
            if not resolved:
                pending.append({
                    "timestamp": row["timestamp"],
                    "source": row["source"],
                    "requester": row["actor"],
                    "content": excerpt,
                })
    return pending


if __name__ == "__main__":
    import argparse, textwrap, json

    parser = argparse.ArgumentParser(description="List potential outstanding tasks assigned to Jourdan in the last N days.")
    parser.add_argument("timeline_csv", type=Path, nargs="?", default=Path("brain/timeline.csv"))
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    rows = load_timeline(args.timeline_csv)
    outstanding = find_outstanding(rows)

    if not outstanding:
        print("No outstanding tasks detected (heuristic).")
    else:
        print(f"Potential outstanding tasks for Jourdan in last {args.days} days:\n")
        for task in outstanding:
            ts = task["timestamp"] or "?"
            print(f"- [{ts}] from {task['requester']} ({task['source']}): {textwrap.shorten(task['content'], width=120)}") 