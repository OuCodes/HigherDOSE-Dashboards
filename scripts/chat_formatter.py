import argparse
import re
from pathlib import Path

HEADER_TEMPLATE = """{title}\n_Exported on {timestamp}_\n\n## 📋 Navigation\n\n| Section | Topic | Participants |\n|---------|-------|-------------|\n"""

SECTION_ROW_TEMPLATE = "| [{name}](#{anchor}) | {topic} | {speaker} |\n"
TURN_SEPARATOR = "---"

SPEAKER_MAP = {
    "user": "### 👤 **User**",
    "cursor": "### 🤖 **Cursor**",
}

def anchor_link(text: str) -> str:
    """Convert a section name to a GitHub-compatible anchor."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)  # remove punctuation/emojis
    text = re.sub(r"\s+", "-", text.strip())  # spaces -> dash
    return text


def parse_blocks(raw: str):
    """Yield (speaker, content) tuples from the raw export."""
    # Split on lines consisting solely of ---
    segments = re.split(r"^---$", raw, flags=re.MULTILINE)
    # Expect pattern: intro, User block, Cursor block, repeated ...
    i = 0
    # Skip any leading empty or header segments until first **User**
    while i < len(segments) and "**User**" not in segments[i] and "**Cursor**" not in segments[i]:
        i += 1
    turn = 0
    while i < len(segments):
        segment = segments[i].strip()
        if segment.startswith("**User**"):
            speaker = "user"
            content = segment.split("**User**", 1)[1].strip()
            yield turn, speaker, content
        elif segment.startswith("**Cursor**"):
            speaker = "cursor"
            content = segment.split("**Cursor**", 1)[1].strip()
            yield turn, speaker, content
            turn += 1  # complete turn after assistant speaks
        i += 1


def build_navigation(turns):
    nav = []
    for turn, speaker, _ in turns:
        if speaker == "user":
            # Use first sentence (max 60 chars) as topic
            topic = _get_topic_snippet(_)
            name = f"Turn {turn+1}"
            nav.append((name, topic, "User"))
    return nav


def _get_topic_snippet(text: str, length: int = 60) -> str:
    snippet = text.strip().splitlines()[0]
    snippet = snippet.strip()
    if len(snippet) > length:
        snippet = snippet[:length - 3] + "..."
    return snippet.replace("|", "\\|")  # escape pipes for MD tables


def format_chat(raw_path: Path, out_path: Path):
    raw_text = raw_path.read_text(encoding="utf-8")

    # Extract title & timestamp from first two lines of file
    lines = raw_text.splitlines()
    title = lines[0].lstrip("# ").strip()
    timestamp = re.sub(r"^_Exported on\s+", "", lines[1]).strip(" _") if len(lines) > 1 else "Unknown"

    # Parse conversation
    turns = list(parse_blocks(raw_text))

    # Build navigation
    nav_rows = "".join(
        SECTION_ROW_TEMPLATE.format(
            name=name,
            anchor=anchor_link(name),
            topic=topic,
            speaker=speaker,
        )
        for name, topic, speaker in build_navigation(turns)
    )

    header = HEADER_TEMPLATE.format(title=title, timestamp=timestamp) + nav_rows + "\n---\n---\n"

    # Build conversation content
    sections = []
    current_section_lines = []
    current_turn = None
    for turn, speaker, content in turns:
        if speaker == "user":
            # start new section
            if current_section_lines:
                sections.append("\n".join(current_section_lines))
                current_section_lines = []
            section_header = f"## Turn {turn+1}"
            current_section_lines.append(section_header)
        current_section_lines.append(SPEAKER_MAP[speaker])
        current_section_lines.append("")
        current_section_lines.append(content)
        current_section_lines.append("")
        if speaker == "cursor":
            # turn ends, insert separator
            current_section_lines.append("---\n---")
    if current_section_lines:
        sections.append("\n".join(current_section_lines))

    output = header + "\n".join(sections)
    out_path.write_text(output, encoding="utf-8")
    print(f"Formatted chat written to {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Format Cursor chat export into enhanced markdown with navigation.")
    parser.add_argument("input", type=Path, help="Path to raw Cursor chat markdown")
    parser.add_argument("output", type=Path, help="Path to save formatted markdown")
    args = parser.parse_args()
    format_chat(args.input, args.output)

if __name__ == "__main__":
    main() 