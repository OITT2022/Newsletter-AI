"""
Generate structured newsletter content from research using Claude API.

Usage:
    python tools/generate_content.py "AI in healthcare" --tone professional
    python tools/generate_content.py "AI in healthcare" --research .tmp/search_results.json --sections 4
"""

import argparse
import json
import os
import sys
from pathlib import Path

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import anthropic
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp"
OUTPUT_FILE = TMP_DIR / "newsletter_content.json"

SYSTEM_PROMPT = """You are a professional Hebrew newsletter writer. Your job is to synthesize research into a compelling, scannable newsletter written entirely in Hebrew.

Rules:
- Write ALL content in Hebrew (subject lines, preview text, hero, sections, closing)
- Use professional, fluent Hebrew — not machine-translated or stilted
- Write in a professional, authoritative tone (unless told otherwise)
- Use natural Hebrew phrasing; avoid literal translations from English
- For technical terms with no common Hebrew equivalent, use the English term in parentheses after the Hebrew description
- Every section MUST cite its source URL
- Keep each section under 150 words — newsletters are skimmed, not read
- Front-load value: lead with the insight, not the background
- Extract concrete numbers and statistics whenever available
- Subject lines must be under 50 characters
- Preview text must be under 100 characters and complement (not repeat) the subject line
- Suggest 2-3 infographic prompts that would visually enhance the content (for AI image generation — write these prompts in the SAME LANGUAGE as the newsletter content, so that any text rendered in the infographic matches the newsletter language)

Output ONLY valid JSON matching the schema below. No markdown, no code fences, no explanation."""

OUTPUT_SCHEMA = """{
  "subject_lines": [
    "Curiosity-driven subject line (under 50 chars)",
    "Direct/value subject line (under 50 chars)",
    "Data-led subject line (under 50 chars)"
  ],
  "preview_text": "Complementary preview text under 100 chars",
  "hero_summary": "2-3 sentence hook explaining why this topic matters right now",
  "sections": [
    {
      "headline": "Section headline",
      "body": "Section body text (under 150 words). Concise, insight-first.",
      "source_url": "https://source-url.com",
      "source_title": "Source Name",
      "key_stat": "73% of companies..." or null
    }
  ],
  "closing": "Brief closing paragraph with a forward-looking takeaway",
  "infographic_prompts": [
    "Description of an infographic that would enhance this newsletter (be specific about data, layout, and visual style)"
  ]
}"""


def load_research(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Format research for the prompt
    lines = []
    for i, item in enumerate(data, 1):
        lines.append(f"Source {i}: {item['title']}")
        lines.append(f"URL: {item['url']}")
        lines.append(f"Content: {item['content'][:2000]}")
        lines.append("")

    return "\n".join(lines)


def generate(topic: str, research_text: str, tone: str, sections: int) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    user_prompt = f"""Topic: {topic}
Tone: {tone}
Number of sections: {sections}

Research:
{research_text}

Generate the newsletter content as JSON matching this schema:
{OUTPUT_SCHEMA}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[
            {"role": "user", "content": user_prompt}
        ],
        system=SYSTEM_PROMPT,
    )

    response_text = message.content[0].text.strip()

    # Handle potential markdown code fences in response
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1]
        if response_text.endswith("```"):
            response_text = response_text[:-3].strip()

    return json.loads(response_text)


def validate_content(content: dict) -> list[str]:
    warnings = []

    if not content.get("subject_lines"):
        warnings.append("Missing subject lines")
    else:
        for sl in content["subject_lines"]:
            if len(sl) > 50:
                warnings.append(f"Subject line too long ({len(sl)} chars): {sl[:30]}...")

    if not content.get("preview_text"):
        warnings.append("Missing preview text")
    elif len(content["preview_text"]) > 100:
        warnings.append(f"Preview text too long ({len(content['preview_text'])} chars)")

    sections = content.get("sections", [])
    if not sections:
        warnings.append("No sections generated")

    for i, section in enumerate(sections, 1):
        if not section.get("source_url"):
            warnings.append(f"Section {i} missing source URL")
        word_count = len(section.get("body", "").split())
        if word_count > 150:
            warnings.append(f"Section {i} too long ({word_count} words)")

    if not content.get("infographic_prompts"):
        warnings.append("No infographic prompts generated")

    return warnings


def main():
    parser = argparse.ArgumentParser(description="Generate newsletter content from research")
    parser.add_argument("topic", help="The newsletter topic")
    parser.add_argument("--research", default=str(TMP_DIR / "search_results.json"),
                        help="Path to research JSON (default: .tmp/search_results.json)")
    parser.add_argument("--tone", default="professional",
                        choices=["professional", "casual", "technical"],
                        help="Newsletter tone (default: professional)")
    parser.add_argument("--sections", type=int, default=4,
                        help="Number of content sections (default: 4)")
    args = parser.parse_args()

    if not Path(args.research).exists():
        print(f"Error: Research file not found: {args.research}", file=sys.stderr)
        print("Run search_topic.py first to generate research data.", file=sys.stderr)
        sys.exit(1)

    print(f"Generating newsletter content for: {args.topic}")
    print(f"Tone: {args.tone}, Sections: {args.sections}")

    research_text = load_research(args.research)
    print(f"Loaded {len(research_text)} chars of research")

    content = generate(args.topic, research_text, args.tone, args.sections)

    warnings = validate_content(content)
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  - {w}")

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, ensure_ascii=False)

    print(f"\nContent saved to: {OUTPUT_FILE}")
    print(f"Subject line options:")
    for i, sl in enumerate(content.get("subject_lines", []), 1):
        print(f"  {i}. {sl}")


if __name__ == "__main__":
    main()
