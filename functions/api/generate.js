/**
 * Newsletter AI - Cloudflare Pages Function
 *
 * Streams SSE events as the pipeline progresses:
 *   event: stage    → current step name
 *   event: result   → final HTML
 *   event: error_msg → error description
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

// ── Format research for prompt ─────────────────────────────────────────────
function formatResearch(results) {
  return results
    .map(
      (r, i) =>
        `Source ${i + 1}: ${r.title}\nURL: ${r.url}\nContent: ${r.content}`
    )
    .join("\n\n");
}

// ── Anthropic API call ─────────────────────────────────────────────────────
async function callClaude(systemPrompt, userPrompt, apiKey, maxTokens = 4096) {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: "claude-sonnet-4-20250514",
      max_tokens: maxTokens,
      system: systemPrompt,
      messages: [{ role: "user", content: userPrompt }],
    }),
  });

  const data = await res.json();
  if (data.error) throw new Error(data.error.message);

  let text = data.content[0].text.trim();
  // Strip markdown code fences
  if (text.startsWith("```")) {
    text = text.split("\n").slice(1).join("\n");
    if (text.endsWith("```")) text = text.slice(0, -3).trim();
  }
  return text;
}

// ── Content Generation ─────────────────────────────────────────────────────
const CONTENT_SYSTEM_PROMPT = `You are a professional Hebrew newsletter writer. Your job is to synthesize research into a compelling, scannable newsletter written entirely in Hebrew.

Rules:
- Write ALL content in Hebrew (subject lines, preview text, hero, sections, closing)
- Use professional, fluent Hebrew — not machine-translated or stilted
- Write in a professional, authoritative tone
- Use natural Hebrew phrasing; avoid literal translations from English
- For technical terms with no common Hebrew equivalent, use the English term in parentheses after the Hebrew description
- Every section MUST cite its source URL
- Keep each section under 150 words — newsletters are skimmed, not read
- Front-load value: lead with the insight, not the background
- Extract concrete numbers and statistics whenever available
- Subject lines must be under 50 characters
- Preview text must be under 100 characters and complement (not repeat) the subject line

Output ONLY valid JSON matching the schema below. No markdown, no code fences, no explanation.`;

const OUTPUT_SCHEMA = `{
  "subject_lines": ["Curiosity-driven subject line (under 50 chars)", "Direct/value subject line (under 50 chars)", "Data-led subject line (under 50 chars)"],
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
  "closing": "Brief closing paragraph with a forward-looking takeaway"
}`;

async function generateContent(topic, research, apiKey) {
  const userPrompt = `Topic: ${topic}
Tone: professional
Number of sections: 4

Research:
${research}

Generate the newsletter content as JSON matching this schema:
${OUTPUT_SCHEMA}`;

  const text = await callClaude(CONTENT_SYSTEM_PROMPT, userPrompt, apiKey);
  return JSON.parse(text);
}

// ── Hebrew Quality Check ───────────────────────────────────────────────────
async function checkHebrew(content, apiKey) {
  const systemPrompt = `You are a Hebrew language expert. Review the newsletter JSON below for grammar, spelling, phrasing, and readability. Return corrected JSON with the EXACT same structure. Fix any issues but preserve meaning. Output ONLY valid JSON, no explanation.`;

  const text = await callClaude(
    systemPrompt,
    JSON.stringify(content, null, 2),
    apiKey,
    8192
  );

  try {
    return JSON.parse(text);
  } catch {
    return content; // If parsing fails, return original
  }
}

// ── HTML Template Rendering ────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function makeUtmParams(topic) {
  const slug = topic
    .toLowerCase()
    .replace(/[^a-z0-9\u0590-\u05ff]+/g, "-")
    .replace(/^-|-$/g, "");
  return `?utm_source=newsletter&utm_medium=email&utm_campaign=${encodeURIComponent(slug)}`;
}

function renderNewsletter(content, topic) {
  const subjectLine = (content.subject_lines || ["Newsletter"])[0];
  const utm = makeUtmParams(topic);

  const sectionsHtml = (content.sections || [])
    .map(
      (s) => `
                    <tr><td class="section">
                        <h2>${escapeHtml(s.headline)}</h2>
                        <p>${escapeHtml(s.body)}</p>
                        ${
                          s.key_stat
                            ? `<div class="stat-callout"><p>${escapeHtml(s.key_stat)}</p></div>`
                            : ""
                        }
                        ${
                          s.source_url
                            ? `<a href="${escapeHtml(s.source_url)}${utm}" class="source-link">${s.source_title ? escapeHtml(s.source_title) + " - " : ""}קראו עוד &larr;</a>`
                            : ""
                        }
                    </td></tr>`
    )
    .join("\n");

  return `<!DOCTYPE html>
<html lang="he" dir="rtl" xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${escapeHtml(subjectLine)}</title>
    <style>
        body, table, td, p, a, li { -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }
        table, td { mso-table-lspace: 0pt; mso-table-rspace: 0pt; }
        img { -ms-interpolation-mode: bicubic; border: 0; outline: none; text-decoration: none; }
        body { margin: 0; padding: 0; width: 100% !important; height: 100% !important; background-color: #f4f4f7; direction: rtl; }
        .email-wrapper { width: 100%; background-color: #f4f4f7; padding: 40px 0; }
        .email-container { max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
        .header { background-color: #1a1a2e; padding: 30px 40px; text-align: center; }
        .header-text { color: #ffffff; font-family: Arial, 'Arial Hebrew', sans-serif; font-size: 14px; letter-spacing: 2px; text-transform: uppercase; margin-top: 10px; }
        .hero { padding: 40px 40px 20px 40px; border-bottom: 3px solid #e8e8ed; text-align: right; }
        .hero h1 { font-family: Arial, 'Arial Hebrew', sans-serif; font-size: 24px; line-height: 1.5; color: #1a1a2e; margin: 0 0 16px 0; font-weight: 700; }
        .hero p { font-family: Arial, 'Arial Hebrew', sans-serif; font-size: 16px; line-height: 1.8; color: #4a4a68; margin: 0; }
        .section { padding: 30px 40px; border-bottom: 1px solid #e8e8ed; text-align: right; }
        .section:last-of-type { border-bottom: none; }
        .section h2 { font-family: Arial, 'Arial Hebrew', sans-serif; font-size: 20px; line-height: 1.4; color: #1a1a2e; margin: 0 0 12px 0; font-weight: 700; }
        .section p { font-family: Arial, 'Arial Hebrew', sans-serif; font-size: 16px; line-height: 1.8; color: #4a4a68; margin: 0 0 12px 0; }
        .section .source-link { font-family: Arial, 'Arial Hebrew', sans-serif; font-size: 14px; color: #6c63ff; text-decoration: none; font-weight: 600; }
        .stat-callout { background-color: #f0efff; border-right: 4px solid #6c63ff; border-left: none; padding: 16px 20px; margin: 16px 0; border-radius: 6px 0 0 6px; text-align: right; }
        .stat-callout p { font-family: Arial, 'Arial Hebrew', sans-serif; font-size: 18px; font-weight: 700; color: #1a1a2e; margin: 0; line-height: 1.5; }
        .closing { padding: 30px 40px; background-color: #fafafc; text-align: right; }
        .closing p { font-family: Arial, 'Arial Hebrew', sans-serif; font-size: 16px; line-height: 1.8; color: #4a4a68; margin: 0; }
        .footer { padding: 30px 40px; background-color: #1a1a2e; text-align: center; }
        .footer p { font-family: Arial, 'Arial Hebrew', sans-serif; font-size: 13px; color: #9999b3; margin: 0 0 8px 0; line-height: 1.6; }
        .footer a { color: #9999b3; text-decoration: underline; }
        @media only screen and (max-width: 620px) {
            .email-container { width: 100% !important; border-radius: 0 !important; }
            .header, .hero, .section, .closing, .footer { padding-left: 20px !important; padding-right: 20px !important; }
            .hero h1 { font-size: 20px !important; }
            .section h2 { font-size: 18px !important; }
        }
    </style>
</head>
<body>
    <div style="display:none;font-size:1px;color:#f4f4f7;line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;">
        ${escapeHtml(content.preview_text || "")}
    </div>
    <table class="email-wrapper" role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" dir="rtl">
        <tr><td align="center">
            <table class="email-container" role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" dir="rtl">
                <tr><td class="header"><div class="header-text">Newsletter</div></td></tr>
                <tr><td class="hero">
                    <h1>${escapeHtml((content.hero_summary || "").slice(0, 80))}${(content.hero_summary || "").length > 80 ? "..." : ""}</h1>
                    <p>${escapeHtml(content.hero_summary || "")}</p>
                </td></tr>
                ${sectionsHtml}
                <tr><td class="closing"><p>${escapeHtml(content.closing || "")}</p></td></tr>
                <tr><td class="footer">
                    <p>קיבלת מייל זה כי נרשמת לניוזלטר שלנו.</p>
                    <p><a href="[UNSUBSCRIBE_LINK]">הסרה מרשימת תפוצה</a> | <a href="[VIEW_IN_BROWSER_LINK]">צפייה בדפדפן</a></p>
                </td></tr>
            </table>
        </td></tr>
    </table>
</body>
</html>`;
}

// ── SSE Helper ─────────────────────────────────────────────────────────────
function sseEvent(event, data) {
  // Encode multi-line data for SSE (each line prefixed with "data:")
  const encoded = String(data).replace(/\n/g, "\ndata: ");
  return `event: ${event}\ndata: ${encoded}\n\n`;
}

// ── Main Handler ───────────────────────────────────────────────────────────
export async function onRequest(context) {
  const url = new URL(context.request.url);
  const topic = url.searchParams.get("topic");

  if (!topic) {
    return new Response("Missing topic", { status: 400 });
  }

  const { TAVILY_API_KEY, ANTHROPIC_API_KEY } = context.env;

  if (!TAVILY_API_KEY || !ANTHROPIC_API_KEY) {
    return new Response("Server misconfigured: missing API keys", {
      status: 500,
    });
  }

  const { readable, writable } = new TransformStream();
  const writer = writable.getWriter();
  const encoder = new TextEncoder();

  const send = (event, data) => writer.write(encoder.encode(sseEvent(event, data)));

  // Run pipeline in background
  (async () => {
    try {
      // Step 1: Research
      await send("stage", "research");
      const results = await searchTopic(topic, TAVILY_API_KEY);
      if (results.length === 0) {
        await send("error_msg", "לא נמצאו תוצאות מחקר לנושא זה");
        await writer.close();
        return;
      }

      // Step 2: Content
      await send("stage", "content");
      const research = formatResearch(results);
      let content = await generateContent(topic, research, ANTHROPIC_API_KEY);

      // Step 3: Hebrew check
      await send("stage", "hebrew");
      content = await checkHebrew(content, ANTHROPIC_API_KEY);

      // Step 4: Render
      await send("stage", "render");
      const html = renderNewsletter(content, topic);

      await send("result", html);
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
      Connection: "keep-alive",
      "Access-Control-Allow-Origin": "*",
    },
  });
}
