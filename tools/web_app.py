"""
Web UI for the Newsletter AI pipeline.

Usage:
    python tools/web_app.py
    python tools/web_app.py --port 5000

Opens a browser-based interface for generating newsletters.
"""

import io
import json
import os
import subprocess
import sys
import threading
from datetime import date
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_file, send_from_directory

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp"
TOOLS_DIR = BASE_DIR / "tools"

app = Flask(__name__, static_folder=str(BASE_DIR / "tools" / "web"), static_url_path="/static")

# Track pipeline progress per session
pipeline_status = {"stage": "idle", "progress": 0, "message": "", "error": ""}
pipeline_lock = threading.Lock()


def update_status(stage: str, progress: int, message: str, error: str = ""):
    with pipeline_lock:
        pipeline_status["stage"] = stage
        pipeline_status["progress"] = progress
        pipeline_status["message"] = message
        pipeline_status["error"] = error


def run_tool(script: str, args: list[str]) -> tuple[bool, str]:
    cmd = [sys.executable, str(TOOLS_DIR / script)] + args
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(BASE_DIR), env=env, timeout=300,
    )
    output = result.stdout + result.stderr
    success = result.returncode == 0
    # Some tools exit 1 due to print encoding but still produce output
    if not success and script in ("generate_content.py", "check_hebrew.py", "render_newsletter.py", "search_topic.py"):
        output_file_map = {
            "search_topic.py": TMP_DIR / "search_results.json",
            "generate_content.py": TMP_DIR / "newsletter_content.json",
            "check_hebrew.py": TMP_DIR / "hebrew_check_report.json",
            "render_newsletter.py": TMP_DIR / f"newsletter_{date.today().isoformat()}.html",
        }
        expected = output_file_map.get(script)
        if expected and expected.exists():
            success = True
    return success, output


def run_pipeline(topic: str):
    try:
        # Stage 1: Clean
        update_status("cleaning", 5, "מנקה קבצים קודמים...")
        for d in (TMP_DIR / "infographics", TMP_DIR / "charts"):
            if d.exists():
                for f in d.glob("*.png"):
                    f.unlink()

        # Stage 2: Research
        update_status("research", 15, "מחפש מידע על הנושא...")
        ok, out = run_tool("search_topic.py", [topic, "--queries", "5"])
        if not ok:
            update_status("error", 15, "", f"שגיאה בשלב המחקר: {out[:300]}")
            return

        # Stage 3: Content Generation
        update_status("content", 35, "יוצר תוכן לניוזלטר...")
        ok, out = run_tool("generate_content.py", [topic, "--tone", "professional", "--sections", "4"])
        if not ok:
            update_status("error", 35, "", f"שגיאה ביצירת תוכן: {out[:300]}")
            return

        # Stage 4: Hebrew Check
        update_status("hebrew", 50, "בודק איכות עברית ומתקן...")
        run_tool("check_hebrew.py", ["--fix"])

        # Stage 5: Infographics
        update_status("visuals", 60, "יוצר אינפוגרפיקות...")
        content_path = TMP_DIR / "newsletter_content.json"
        infographic_ok = False
        if content_path.exists():
            with open(content_path, "r", encoding="utf-8") as f:
                content = json.load(f)
            prompts = content.get("infographic_prompts", [])
            for i, prompt in enumerate(prompts[:3]):
                update_status("visuals", 60 + (i * 5), f"אינפוגרפיקה {i + 1} מתוך {min(len(prompts), 3)}...")
                ok, _ = run_tool("generate_infographic.py", [prompt, "--style", "modern"])
                if ok:
                    infographic_ok = True

        # Stage 6: Charts (fallback or supplement)
        if not infographic_ok:
            update_status("visuals", 75, "יוצר גרפים...")
            sections = content.get("sections", [])
            for i, section in enumerate(sections[:2]):
                stat = section.get("key_stat", "")
                if stat:
                    run_tool("generate_chart.py", [
                        "stat_card",
                        "--data", json.dumps({"label": section.get("headline", ""), "value": stat}, ensure_ascii=False),
                        "--title", section.get("headline", ""),
                    ])

        # Stage 7: Render
        update_status("render", 85, "מרכיב את הניוזלטר...")
        ok, out = run_tool("render_newsletter.py", ["--topic", topic])
        if not ok:
            update_status("error", 85, "", f"שגיאה בהרכבת הניוזלטר: {out[:300]}")
            return

        update_status("done", 100, "הניוזלטר מוכן!")
    except Exception as e:
        update_status("error", 0, "", str(e))


@app.route("/")
def index():
    return send_from_directory(str(TOOLS_DIR / "web"), "index.html")


@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json()
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "נושא ריק"}), 400

    if pipeline_status["stage"] not in ("idle", "done", "error"):
        return jsonify({"error": "עיבוד כבר רץ, נא להמתין"}), 409

    update_status("starting", 0, "מתחיל...")
    thread = threading.Thread(target=run_pipeline, args=(topic,), daemon=True)
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/status")
def status():
    with pipeline_lock:
        return jsonify(dict(pipeline_status))


@app.route("/api/preview")
def preview():
    today = date.today().isoformat()
    html_path = TMP_DIR / f"newsletter_{today}.html"
    if not html_path.exists():
        return Response("", status=404)
    return send_file(str(html_path), mimetype="text/html")


@app.route("/api/download")
def download():
    today = date.today().isoformat()
    html_path = TMP_DIR / f"newsletter_{today}.html"
    if not html_path.exists():
        return Response("", status=404)
    return send_file(str(html_path), as_attachment=True, download_name=f"newsletter_{today}.html")


@app.route("/api/content")
def content():
    content_path = TMP_DIR / "newsletter_content.json"
    if not content_path.exists():
        return Response("{}", status=404, mimetype="application/json")
    with open(content_path, "r", encoding="utf-8") as f:
        return Response(f.read(), mimetype="application/json; charset=utf-8")


if __name__ == "__main__":
    import argparse
    import webbrowser

    parser = argparse.ArgumentParser(description="Newsletter AI Web UI")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{args.port}")).start()

    print(f"Newsletter AI Web UI: http://localhost:{args.port}")
    app.run(host="127.0.0.1", port=args.port, debug=False)
