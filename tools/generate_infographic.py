"""
Generate infographic images using Google Gemini API (Nano Banana 2).

Usage:
    python tools/generate_infographic.py "A clean infographic showing AI adoption rates across industries"
    python tools/generate_infographic.py "..." --output .tmp/infographics/infographic_1.png
    python tools/generate_infographic.py "..." --style minimalist
"""

import argparse
import os
import sys
from pathlib import Path

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp"
OUTPUT_DIR = TMP_DIR / "infographics"


def generate_infographic(prompt: str, output_path: str, style: str = "modern") -> bool:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    import re
    has_hebrew = bool(re.search(r'[\u0590-\u05FF]', prompt))

    hebrew_rules = (
        "\n\nCRITICAL HEBREW TEXT RULES:"
        "\n- Any Hebrew text MUST be written RIGHT-TO-LEFT (RTL). This is the #1 priority."
        "\n- Hebrew reads from RIGHT to LEFT. The first letter of a word appears on the RIGHT side."
        "\n- Example: The word 'שלום' starts with 'ש' on the right, then 'ל', 'ו', 'ם' going left."
        "\n- DO NOT mirror or reverse Hebrew letters. Each letter must face its correct direction."
        "\n- If you cannot render Hebrew correctly, use NUMBERS and ICONS instead of Hebrew text."
        "\n- Prefer minimal text — use icons, arrows, and visual elements over words."
    ) if has_hebrew else ""

    full_prompt = (
        f"Create a clean, professional infographic in a {style} style. "
        f"White or light background. Newsletter-ready, high quality, no watermarks. "
        f"Aspect ratio suitable for email newsletter (roughly 560px wide). "
        f"Prefer ICONS, NUMBERS, and VISUAL ELEMENTS over text. Keep any text extremely short (1-3 words max per label)."
        f"{hebrew_rules}"
        f"\n\nContent: {prompt}"
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=full_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    # Extract image from response
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            image_data = part.inline_data.data
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "wb") as f:
                f.write(image_data)
            print(f"Infographic saved: {out}")
            return True

    print("Error: No image generated in response", file=sys.stderr)
    return False


def main():
    parser = argparse.ArgumentParser(description="Generate infographic via Gemini (Nano Banana 2)")
    parser.add_argument("prompt", help="Description of the infographic to generate")
    parser.add_argument("--output", default="", help="Output file path (default: auto-numbered in .tmp/infographics/)")
    parser.add_argument("--style", default="modern", choices=["modern", "minimalist", "tech", "corporate"],
                        help="Visual style (default: modern)")
    args = parser.parse_args()

    if args.output:
        output_path = args.output
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        existing = list(OUTPUT_DIR.glob("infographic_*.png"))
        next_num = len(existing) + 1
        output_path = str(OUTPUT_DIR / f"infographic_{next_num}.png")

    success = generate_infographic(args.prompt, output_path, args.style)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
