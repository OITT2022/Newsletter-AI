"""
Render the final newsletter HTML from content JSON and images.

Usage:
    python tools/render_newsletter.py
    python tools/render_newsletter.py --content .tmp/newsletter_content.json --logo Logo/logo.png
"""

import argparse
import base64
import io
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from jinja2 import Environment, FileSystemLoader
from premailer import transform

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def encode_image_b64(image_path: str) -> str:
    path = Path(image_path)
    if not path.exists():
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def collect_images(directory: Path, pattern: str = "*.png") -> list[str]:
    if not directory.exists():
        return []
    images = sorted(directory.glob(pattern))
    return [encode_image_b64(str(img)) for img in images if img.stat().st_size > 0]


def make_utm_params(topic: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return f"?utm_source=newsletter&utm_medium=email&utm_campaign={slug}"


def render(content: dict, logo_path: str = "", topic: str = "") -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("newsletter_base.html")

    # Encode images
    logo_b64 = encode_image_b64(logo_path) if logo_path else ""
    infographics = collect_images(TMP_DIR / "infographics")
    charts = collect_images(TMP_DIR / "charts")

    # Pick first subject line
    subject_lines = content.get("subject_lines", ["Newsletter"])
    subject_line = subject_lines[0] if subject_lines else "Newsletter"

    utm_params = make_utm_params(topic) if topic else ""

    html = template.render(
        subject_line=subject_line,
        preview_text=content.get("preview_text", ""),
        hero_summary=content.get("hero_summary", ""),
        sections=content.get("sections", []),
        closing=content.get("closing", ""),
        logo_b64=logo_b64,
        infographics=infographics,
        charts=charts,
        utm_params=utm_params,
    )

    # Inline CSS for email compatibility
    html = transform(html, keep_style_tags=True, strip_important=False)

    return html


def main():
    parser = argparse.ArgumentParser(description="Render newsletter HTML")
    parser.add_argument("--content", default=str(TMP_DIR / "newsletter_content.json"),
                        help="Path to content JSON")
    parser.add_argument("--logo", default="", help="Path to logo image")
    parser.add_argument("--topic", default="", help="Topic for UTM tracking params")
    parser.add_argument("--subject-index", type=int, default=0,
                        help="Which subject line to use (0-2)")
    args = parser.parse_args()

    content_path = Path(args.content)
    if not content_path.exists():
        print(f"Error: Content file not found: {args.content}")
        print("Run generate_content.py first.")
        return

    with open(content_path, "r", encoding="utf-8") as f:
        content = json.load(f)

    # Allow overriding subject line choice
    if args.subject_index and content.get("subject_lines"):
        idx = min(args.subject_index, len(content["subject_lines"]) - 1)
        content["subject_lines"] = [content["subject_lines"][idx]] + content["subject_lines"]

    # Find logo
    logo_path = args.logo
    if not logo_path:
        logo_dir = BASE_DIR / "Logo"
        if logo_dir.exists():
            for ext in ["png", "jpg", "jpeg", "svg"]:
                candidates = list(logo_dir.glob(f"*.{ext}"))
                if candidates:
                    logo_path = str(candidates[0])
                    break

    html = render(content, logo_path=logo_path, topic=args.topic)

    today = date.today().isoformat()
    output_path = TMP_DIR / f"newsletter_{today}.html"
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Newsletter rendered: {output_path}")
    print(f"Subject: {content.get('subject_lines', [''])[0]}")

    infographic_count = len(list((TMP_DIR / "infographics").glob("*.png"))) if (TMP_DIR / "infographics").exists() else 0
    chart_count = len(list((TMP_DIR / "charts").glob("*.png"))) if (TMP_DIR / "charts").exists() else 0
    print(f"Images: logo={'yes' if logo_path else 'no'}, infographics={infographic_count}, charts={chart_count}")


if __name__ == "__main__":
    main()
