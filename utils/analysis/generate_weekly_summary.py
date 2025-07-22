import argparse
from datetime import datetime, timedelta
from pathlib import Path
import re
import textwrap
import pandas as pd

CATEGORIES = {
    "Wins & Updates": [
        r"\bwin\b",
        r"increase",
        r"improv",
        r"up \d",  # e.g., up 6 %
        r"lift",
        r"spike",
    ],
    "Challenges": [
        r"\bissue\b",
        r"\bproblem\b",
        r"concern",
        r"down",
        r"dip",
        r"drop",
        r"challenge",
        r"cac",
    ],
    "Opportunities & Solutions": [
        r"opportun",
        r"could",
        r"should",
        r"scale",
        r"optimi",
        r"idea",
        r"test",
        r"solution",
    ],
    "Weekly Task List & July Priorities": [
        r"todo",
        r"task",
        r"priority",
        r"follow up",
        r"action item",
        r"need to",
        r"i will",
        r"we will",
    ],
    "Affiliate Partnership Insights": [
        r"affiliate",
        r"awin",
        r"refersion",
        r"partner",
    ],
    "Creative Reporting": [
        r"creative",
        r"asset",
        r"content",
        r"video",
        r"static",
        r"concept",
    ],
    "Website & CRO": [
        r"cro",
        r"landing page",
        r"conversion",
        r"website",
        r"site",
        r"funnel",
    ],
    "Notes on Creative Testing Constraints": [
        r"assets available",
        r"< ?\d+ ?",
        r"constraint",
        r"testing",
        r"creative type",
    ],
    "Next Steps / Action Items": [
        r"next steps",
        r"action items",
        r"plan",
        r"roadmap",
        r"upcoming",
    ],
}


def compile_category_patterns():
    compiled = {}
    for cat, pats in CATEGORIES.items():
        compiled[cat] = [re.compile(pat, re.IGNORECASE) for pat in pats]
    return compiled


PATTERNS = compile_category_patterns()


def extract_insights(df: pd.DataFrame, days: int = 7):
    window_start = datetime.now() - timedelta(days=days)
    recent = df[df["timestamp"] >= window_start]

    insights = {cat: [] for cat in CATEGORIES}

    for _, row in recent.iterrows():
        content_lower = str(row["content"]).lower()
        for cat, regexes in PATTERNS.items():
            if any(r.search(content_lower) for r in regexes):
                bullet = f"[{row['timestamp'].strftime('%Y-%m-%d %H:%M')}] {row['actor']}: {textwrap.shorten(row['content'], width=140)}"
                insights[cat].append(bullet)
                break  # assign to first matching category
    return insights


def generate_markdown(insights: dict, days: int):
    md_lines = []
    md_lines.append(f"# Executive Summary – Last {days} Days ({datetime.now().strftime('%Y-%m-%d')})\n")
    md_lines.append("---\n")

    # Simple narrative summary
    total_messages = sum(len(v) for v in insights.values())
    md_lines.append(f"Analysed {total_messages} relevant Slack + Email messages. Key takeaways are grouped below.\n\n")

    for cat, bullets in insights.items():
        if not bullets:
            continue
        md_lines.append(f"## {cat}\n")
        for b in bullets[:10]:
            md_lines.append(f"- {b}")
        md_lines.append("")

    return "\n".join(md_lines)


def main(csv_path: Path, output_path: Path | None, days: int):
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    insights = extract_insights(df, days)
    md = generate_markdown(insights, days)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md, encoding="utf-8")
        print(f"Report written to {output_path}")
    else:
        print(md)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate executive summary from timeline CSV for last N days.")
    parser.add_argument("--csv", type=Path, default=Path("brain/timeline.csv"), help="Timeline CSV path")
    parser.add_argument("--days", type=int, default=7, help="Lookback window in days")
    parser.add_argument("--output", type=Path, help="Optional markdown file to write")
    args = parser.parse_args()

    main(args.csv, args.output, args.days) 