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

    full_prompt = (
        f"Generate a beautiful, professional illustration or photo-realistic image in a {style} style. "
        f"CRITICAL: The image must contain ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO NUMBERS, NO LABELS. "
        f"Only visual elements: illustrations, icons, photos, patterns, gradients. "
        f"Clean modern style, white or light background, high quality, no watermarks. "
        f"Aspect ratio suitable for email newsletter (roughly 560px wide, 300px tall). "
        f"\n\nSubject: {prompt}"
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
