"""Test that all APIs and assets are configured correctly."""
import io
import os
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv

# Load .env from project root
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

results = []

def test(name, func):
    try:
        msg = func()
        results.append((name, True, msg))
        print(f"  [PASS] {name}: {msg}")
    except Exception as e:
        results.append((name, False, str(e)))
        print(f"  [FAIL] {name}: {e}")


# --- 1. Tavily API ---
def test_tavily():
    from tavily import TavilyClient
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        raise ValueError("TAVILY_API_KEY not set in .env")
    client = TavilyClient(api_key=key)
    resp = client.search("test query", max_results=1)
    if resp and "results" in resp and len(resp["results"]) > 0:
        return f"OK - got {len(resp['results'])} result(s)"
    raise ValueError("Search returned no results")

print("\n1. Tavily (web research)...")
test("Tavily API", test_tavily)


# --- 2. Anthropic API ---
def test_anthropic():
    import anthropic
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set in .env")
    client = anthropic.Anthropic(api_key=key)
    resp = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=50,
        messages=[{"role": "user", "content": "Say 'API test OK' and nothing else."}]
    )
    text = resp.content[0].text
    return f"OK - response: {text.strip()}"

print("\n2. Anthropic (content generation)...")
test("Anthropic API", test_anthropic)


# --- 3. Google Gemini API ---
def test_gemini():
    import google.generativeai as genai
    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("GOOGLE_API_KEY not set in .env")
    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-2.0-flash")
    resp = model.generate_content("Say 'API test OK' and nothing else.")
    return f"OK - response: {resp.text.strip()}"

print("\n3. Google Gemini (infographic generation)...")
test("Google Gemini API", test_gemini)


# --- 4. Logo file ---
def test_logo():
    from PIL import Image
    logo_dir = project_root / "Logo"
    if not logo_dir.exists():
        raise FileNotFoundError("Logo/ directory not found")
    images = list(logo_dir.glob("*.png")) + list(logo_dir.glob("*.jpg")) + list(logo_dir.glob("*.svg"))
    if not images:
        raise FileNotFoundError("No image files found in Logo/")
    img = Image.open(images[0])
    return f"OK - {images[0].name} ({img.size[0]}x{img.size[1]})"

print("\n4. Logo asset...")
test("Logo file", test_logo)


# --- 5. Jinja2 / Premailer (local libs) ---
def test_html_libs():
    from jinja2 import Template
    from premailer import transform
    html = Template("<h1>{{ title }}</h1>").render(title="Test")
    result = transform(html)
    if "<h1>" in result:
        return "OK - Jinja2 + Premailer working"
    raise ValueError("HTML transform failed")

print("\n5. HTML libraries (Jinja2 + Premailer)...")
test("HTML libs", test_html_libs)


# --- 6. Matplotlib + Pillow ---
def test_chart_libs():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image
    import io
    fig, ax = plt.subplots()
    ax.bar(["A", "B"], [1, 2])
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    img = Image.open(buf)
    return f"OK - generated test chart ({img.size[0]}x{img.size[1]})"

print("\n6. Chart libraries (Matplotlib + Pillow)...")
test("Chart libs", test_chart_libs)


# --- Summary ---
print("\n" + "=" * 50)
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f"Results: {passed}/{total} passed")
if passed < total:
    print("\nFailed tests:")
    for name, ok, msg in results:
        if not ok:
            print(f"  - {name}: {msg}")
    sys.exit(1)
else:
    print("All systems go!")
    sys.exit(0)
