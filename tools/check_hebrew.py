"""
Check and improve Hebrew text quality in newsletter content using Claude API.

Catches grammar errors, unnatural phrasing, inconsistent tone, and suggests improvements.

Usage:
    python tools/check_hebrew.py
    python tools/check_hebrew.py --content .tmp/newsletter_content.json
    python tools/check_hebrew.py --fix  # Auto-apply corrections
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
DEFAULT_CONTENT = TMP_DIR / "newsletter_content.json"

SYSTEM_PROMPT = """You are a professional Hebrew language editor and proofreader.
You review newsletter content written in Hebrew and check for:

1. **Grammar errors** — incorrect verb conjugations, gender mismatches, preposition errors
2. **Spelling mistakes** — typos, incorrect niqqud-less spelling
3. **Unnatural phrasing** — literal translations from English, stilted or robotic Hebrew
4. **Tone consistency** — ensure professional yet accessible tone throughout
5. **Readability** — sentences that are too long, unclear structure, missing punctuation
6. **Technical terms** — verify English terms in parentheses are used correctly

For each issue found, provide:
- The problematic text
- The corrected version
- A brief explanation (in Hebrew)

Output ONLY valid JSON. No markdown, no code fences."""

CHECK_SCHEMA = """{
  "overall_score": 85,
  "summary": "סיכום קצר של איכות הטקסט בעברית",
  "issues": [
    {
      "field": "sections[0].body",
      "original": "הטקסט המקורי הבעייתי",
      "corrected": "הטקסט המתוקן",
      "category": "grammar|spelling|phrasing|tone|readability|technical",
      "explanation": "הסבר קצר בעברית"
    }
  ],
  "corrected_content": {
    "subject_lines": ["..."],
    "preview_text": "...",
    "hero_summary": "...",
    "sections": [{"headline": "...", "body": "...", "source_url": "...", "source_title": "...", "key_stat": "..."}],
    "closing": "...",
    "infographic_prompts": ["..."]
  }
}"""


def load_content(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_text_for_review(content: dict) -> str:
    """Extract all Hebrew text fields for review."""
    parts = []

    for i, sl in enumerate(content.get("subject_lines", [])):
        parts.append(f"subject_lines[{i}]: {sl}")

    parts.append(f"preview_text: {content.get('preview_text', '')}")
    parts.append(f"hero_summary: {content.get('hero_summary', '')}")

    for i, section in enumerate(content.get("sections", [])):
        parts.append(f"sections[{i}].headline: {section.get('headline', '')}")
        parts.append(f"sections[{i}].body: {section.get('body', '')}")
        if section.get("key_stat"):
            parts.append(f"sections[{i}].key_stat: {section['key_stat']}")

    parts.append(f"closing: {content.get('closing', '')}")

    return "\n\n".join(parts)


def check_hebrew(content: dict) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    text_for_review = extract_text_for_review(content)

    user_prompt = f"""Review the following Hebrew newsletter content for quality.
Check grammar, spelling, natural phrasing, tone consistency, and readability.
Return the full corrected content in the corrected_content field.

Newsletter content:
{text_for_review}

Full original JSON (preserve structure, URLs, and infographic_prompts):
{json.dumps(content, ensure_ascii=False, indent=2)}

Output JSON matching this schema:
{CHECK_SCHEMA}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        messages=[{"role": "user", "content": user_prompt}],
        system=SYSTEM_PROMPT,
    )

    response_text = message.content[0].text.strip()

    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1]
        if response_text.endswith("```"):
            response_text = response_text[:-3].strip()

    return json.loads(response_text)


def main():
    parser = argparse.ArgumentParser(description="Check Hebrew quality in newsletter content")
    parser.add_argument("--content", default=str(DEFAULT_CONTENT),
                        help="Path to content JSON (default: .tmp/newsletter_content.json)")
    parser.add_argument("--fix", action="store_true",
                        help="Auto-apply corrections to the content file")
    args = parser.parse_args()

    content_path = Path(args.content)
    if not content_path.exists():
        print(f"Error: Content file not found: {args.content}", file=sys.stderr)
        print("Run generate_content.py first.", file=sys.stderr)
        sys.exit(1)

    content = load_content(str(content_path))
    print("Checking Hebrew quality...")

    result = check_hebrew(content)

    score = result.get("overall_score", "?")
    issues = result.get("issues", [])

    print(f"\nHebrew Quality Score: {score}/100")
    print(f"Summary: {result.get('summary', '')}")

    if issues:
        print(f"\nFound {len(issues)} issue(s):\n")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. [{issue['category']}] {issue['field']}")
            print(f"     Before: {issue['original']}")
            print(f"     After:  {issue['corrected']}")
            print(f"     Why:    {issue['explanation']}")
            print()
    else:
        print("\nNo issues found!")

    if args.fix and result.get("corrected_content"):
        corrected = result["corrected_content"]
        with open(content_path, "w", encoding="utf-8") as f:
            json.dump(corrected, f, indent=2, ensure_ascii=False)
        print(f"Corrections applied to: {content_path}")
    elif issues and not args.fix:
        report_path = TMP_DIR / "hebrew_check_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Full report saved to: {report_path}")
        print("Run with --fix to auto-apply corrections.")


if __name__ == "__main__":
    main()
