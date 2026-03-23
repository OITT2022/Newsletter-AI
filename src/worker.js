/**
 * Newsletter AI - Cloudflare Worker
 *
 * Routes:
 *   GET  /                → static index.html (served by assets binding)
 *   GET  /api/generate    → SSE streaming pipeline
 *
 * Environment variables (set in Cloudflare Dashboard):
 *   TAVILY_API_KEY, ANTHROPIC_API_KEY
 */

// ── Tavily Search ──────────────────────────────────────────────────────────
async function searchTopic(topic, apiKey) {
  const queries = [
    topic,
    `${topic} statistics 2026`,
    `${topic} latest developments 2026`,
    `${topic} trends and analysis`,
    `${topic} expert opinions insights`,
  ];

  const allResults = [];
  const seenUrls = new Set();

  for (const query of queries) {
    try {
      const res = await fetch("https://api.tavily.com/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: apiKey,
          query,
          search_depth: "advanced",
          max_results: 5,
        }),
      });
      const data = await res.json();
      for (const r of data.results || []) {
        if (!seenUrls.has(r.url)) {
          seenUrls.add(r.url);
          allResults.push({
            title: r.title || "",
            url: r.url || "",
            content: (r.content || "").slice(0, 2000),
            score: r.score || 0,
          });
        }
      }
    } catch (e) {
      // Continue with other queries
    }
  }

  allResults.sort((a, b) => b.score - a.score);
  return allResults;
}

function formatResearch(results) {
  // Limit total research text to ~3000 chars to stay within API rate limits
  const maxTotal = 3000;
  let total = 0;
  const lines = [];
  for (let i = 0; i < results.length && total < maxTotal; i++) {
    const r = results[i];
    const contentSlice = r.content.slice(0, Math.min(800, maxTotal - total));
    const line = `Source ${i + 1}: ${r.title}\nURL: ${r.url}\nContent: ${contentSlice}`;
    lines.push(line);
    total += line.length;
  }
  return lines.join("\n\n");
}

// ── Anthropic API ──────────────────────────────────────────────────────────
async function callClaude(systemPrompt, userPrompt, apiKey, maxTokens = 4096, model = "claude-sonnet-4-20250514") {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model,
      max_tokens: maxTokens,
      system: systemPrompt,
      messages: [{ role: "user", content: userPrompt }],
    }),
  });

  const data = await res.json();
  if (data.error) throw new Error(data.error.message);

  let text = data.content[0].text.trim();
  if (text.startsWith("```")) {
    text = text.split("\n").slice(1).join("\n");
    if (text.endsWith("```")) text = text.slice(0, -3).trim();
  }
  return text;
}

// ── Content Generation ─────────────────────────────────────────────────────
const CONTENT_SYSTEM = `You are a professional Hebrew newsletter writer. Your job is to synthesize research into a compelling, scannable newsletter written entirely in Hebrew.

Rules:
- Write ALL content in Hebrew (subject lines, preview text, hero, sections, closing)
- Use professional, fluent Hebrew — not machine-translated or stilted
- Write in a professional, authoritative tone
- Use natural Hebrew phrasing; avoid literal translations from English
- For technical terms with no common Hebrew equivalent, use the English term in parentheses after the Hebrew description
- Every section MUST cite its source URL
- Keep each section under 150 words
- Front-load value: lead with the insight, not the background
- Extract concrete numbers and statistics whenever available
- Subject lines must be under 50 characters
- Preview text must be under 100 characters and complement (not repeat) the subject line

Output ONLY valid JSON matching the schema below. No markdown, no code fences, no explanation.`;

const SCHEMA = `{
  "subject_lines": ["Under 50 chars each"],
  "preview_text": "Under 100 chars",
  "hero_summary": "2-3 sentence hook",
  "sections": [{"headline":"...","body":"under 150 words","source_url":"https://...","source_title":"...","key_stat":"... or null"}],
  "closing": "Forward-looking takeaway"
}`;

async function generateContent(topic, research, apiKey) {
  const prompt = `Topic: ${topic}\nTone: professional\nNumber of sections: 4\n\nResearch:\n${research}\n\nGenerate the newsletter content as JSON matching this schema:\n${SCHEMA}`;
  const text = await callClaude(CONTENT_SYSTEM, prompt, apiKey);
  return JSON.parse(text);
}

async function checkHebrew(content, apiKey) {
  const sys = `You are a Hebrew language expert. Review the newsletter JSON below for grammar, spelling, phrasing, and readability. Return corrected JSON with the EXACT same structure. Fix any issues but preserve meaning. Output ONLY valid JSON, no explanation.`;
  const text = await callClaude(sys, JSON.stringify(content, null, 2), apiKey, 2048);
  try { return JSON.parse(text); } catch { return content; }
}

// ── HTML Rendering ─────────────────────────────────────────────────────────
function esc(str) {
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function renderNewsletter(content, topic) {
  const subj = (content.subject_lines || ["Newsletter"])[0];
  const slug = topic.toLowerCase().replace(/[^a-z0-9\u0590-\u05ff]+/g, "-").replace(/^-|-$/g, "");
  const utm = `?utm_source=newsletter&utm_medium=email&utm_campaign=${encodeURIComponent(slug)}`;

  const sections = (content.sections || []).map(s => `
    <tr><td style="padding:30px 40px;border-bottom:1px solid #e8e8ed;text-align:right;font-family:Arial,'Arial Hebrew',sans-serif;">
      <h2 style="font-size:20px;line-height:1.4;color:#1a1a2e;margin:0 0 12px 0;font-weight:700;">${esc(s.headline)}</h2>
      <p style="font-size:16px;line-height:1.8;color:#4a4a68;margin:0 0 12px 0;">${esc(s.body)}</p>
      ${s.key_stat ? `<div style="background-color:#f0efff;border-right:4px solid #6c63ff;padding:16px 20px;margin:16px 0;border-radius:6px 0 0 6px;"><p style="font-size:18px;font-weight:700;color:#1a1a2e;margin:0;line-height:1.5;">${esc(s.key_stat)}</p></div>` : ""}
      ${s.source_url ? `<a href="${esc(s.source_url)}${utm}" style="font-size:14px;color:#6c63ff;text-decoration:none;font-weight:600;">${s.source_title ? esc(s.source_title) + " - " : ""}קראו עוד &larr;</a>` : ""}
    </td></tr>`).join("\n");

  return `<!DOCTYPE html>
<html lang="he" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>${esc(subj)}</title>
<style>body{margin:0;padding:0;width:100%!important;background:#f4f4f7;direction:rtl}
@media only screen and (max-width:620px){.ec{width:100%!important;border-radius:0!important}.sec{padding:20px!important}}</style></head>
<body><div style="display:none;font-size:1px;color:#f4f4f7;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">${esc(content.preview_text || "")}</div>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background:#f4f4f7;padding:40px 0;" dir="rtl">
<tr><td align="center">
<table class="ec" role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.06);" dir="rtl">
<tr><td style="background:#1a1a2e;padding:30px 40px;text-align:center;"><div style="color:#fff;font-family:Arial,sans-serif;font-size:14px;letter-spacing:2px;text-transform:uppercase;">Newsletter</div></td></tr>
<tr><td class="sec" style="padding:40px 40px 20px;border-bottom:3px solid #e8e8ed;text-align:right;font-family:Arial,'Arial Hebrew',sans-serif;">
<h1 style="font-size:24px;line-height:1.5;color:#1a1a2e;margin:0 0 16px;font-weight:700;">${esc((content.hero_summary||"").slice(0,80))}${(content.hero_summary||"").length>80?"...":""}</h1>
<p style="font-size:16px;line-height:1.8;color:#4a4a68;margin:0;">${esc(content.hero_summary||"")}</p>
</td></tr>
${sections}
<tr><td class="sec" style="padding:30px 40px;background:#fafafc;text-align:right;font-family:Arial,'Arial Hebrew',sans-serif;">
<p style="font-size:16px;line-height:1.8;color:#4a4a68;margin:0;">${esc(content.closing||"")}</p></td></tr>
<tr><td style="padding:30px 40px;background:#1a1a2e;text-align:center;font-family:Arial,'Arial Hebrew',sans-serif;">
<p style="font-size:13px;color:#9999b3;margin:0 0 8px;">קיבלת מייל זה כי נרשמת לניוזלטר שלנו.</p>
<p style="font-size:13px;color:#9999b3;margin:0;"><a href="[UNSUBSCRIBE_LINK]" style="color:#9999b3;text-decoration:underline;">הסרה מרשימת תפוצה</a> | <a href="[VIEW_IN_BROWSER_LINK]" style="color:#9999b3;text-decoration:underline;">צפייה בדפדפן</a></p>
</td></tr></table></td></tr></table></body></html>`;
}

// ── Delay (respect rate limits) ─────────────────────────────────────────────
function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── SSE ────────────────────────────────────────────────────────────────────
function sseEvent(event, data) {
  return `event: ${event}\ndata: ${String(data).replace(/\n/g, "\ndata: ")}\n\n`;
}

// ── Worker Entry Point ─────────────────────────────────────────────────────
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // API route
    if (url.pathname === "/api/generate") {
      const topic = url.searchParams.get("topic");
      if (!topic) return new Response("Missing topic", { status: 400 });
      if (!env.TAVILY_API_KEY || !env.ANTHROPIC_API_KEY) {
        return new Response("Server misconfigured: missing API keys", { status: 500 });
      }

      const { readable, writable } = new TransformStream();
      const writer = writable.getWriter();
      const enc = new TextEncoder();
      const send = (ev, d) => writer.write(enc.encode(sseEvent(ev, d)));

      (async () => {
        try {
          await send("stage", "research");
          const results = await searchTopic(topic, env.TAVILY_API_KEY);
          if (!results.length) { await send("error_msg", "לא נמצאו תוצאות מחקר"); await writer.close(); return; }

          await send("stage", "content");
          let content = await generateContent(topic, formatResearch(results), env.ANTHROPIC_API_KEY);

          await delay(5000); // Wait 5s to respect rate limits between calls

          await send("stage", "hebrew");
          content = await checkHebrew(content, env.ANTHROPIC_API_KEY);

          await send("stage", "render");
          await send("result", renderNewsletter(content, topic));
        } catch (e) {
          await send("error_msg", e.message || "שגיאה לא צפויה");
        } finally {
          await writer.close();
        }
      })();

      return new Response(readable, {
        headers: {
          "Content-Type": "text/event-stream; charset=utf-8",
          "Cache-Control": "no-cache",
          "Access-Control-Allow-Origin": "*",
        },
      });
    }

    // Everything else → static assets (handled by Cloudflare assets binding)
    return env.ASSETS.fetch(request);
  },
};
