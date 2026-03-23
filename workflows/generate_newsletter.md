# Generate Newsletter

## Objective
Given a topic, research it, generate professional content, create infographics using Nano Banana 2, and produce a ready-to-send HTML newsletter delivered via Gmail.

## Required Inputs
- **topic**: The newsletter subject (e.g., "AI in healthcare Q1 2026")
- **tone** (optional): "professional" | "casual" | "technical" (default: professional)
- **sections** (optional): Number of content sections (default: 4)
- **recipients** (optional): Email address(es) or path to recipients JSON file

## Required API Keys (.env)
- `TAVILY_API_KEY` — web research
- `ANTHROPIC_API_KEY` — content generation
- `GOOGLE_API_KEY` — Gemini API for Nano Banana 2 infographics

## Required Auth Files
- `credentials.json` — Google OAuth for Gmail API (download from Google Cloud Console)
- `token.json` — auto-generated on first Gmail send

---

## Workflow Steps

### Step 1: Research
1. Break the topic into 3-5 search queries:
   - The main topic verbatim
   - Topic + "statistics [current year]"
   - Topic + "latest developments [current year]"
   - Topic + "trends and analysis"
   - Topic + "expert opinions insights"
2. Run: `python tools/search_topic.py "<topic>" --queries 5`
3. Review `.tmp/search_results.json` — check result count and relevance
4. If any source looks valuable but has truncated content, deep-scrape it:
   `python tools/scrape_url.py "<url>" --output .tmp/scraped_article.json`
5. Merge deep-scraped content into search_results.json if needed

**Output:** `.tmp/search_results.json`

### Step 2: Content Generation
1. Run: `python tools/generate_content.py "<topic>" --tone professional --sections 4`
2. Review `.tmp/newsletter_content.json` and verify:
   - [ ] Each section has a source URL
   - [ ] At least 2 quantitative data points exist
   - [ ] All 3 subject lines are under 50 characters
   - [ ] Preview text is under 100 characters
   - [ ] No section exceeds 150 words
   - [ ] Infographic prompts are specific and actionable
3. If quality is insufficient, re-run with adjusted parameters or manually edit the JSON

**Output:** `.tmp/newsletter_content.json`

### Step 2.5: Hebrew Quality Check
1. Run: `python tools/check_hebrew.py`
2. Review the quality score and issues found
3. If score < 80 or critical grammar issues exist, apply fixes:
   `python tools/check_hebrew.py --fix`
4. Re-review the corrected content in `.tmp/newsletter_content.json`

**Output:** Corrected `.tmp/newsletter_content.json` + `.tmp/hebrew_check_report.json`

### Step 3: Visuals
1. Read the `infographic_prompts` from the content JSON
2. For each prompt (max 3), generate an infographic:
   `python tools/generate_infographic.py "<prompt>" --style modern`
3. Check if any sections have `key_stat` values worth charting:
   - Single numbers → `stat_card` type
   - Comparisons → `bar` type
   - Trends over time → `line` type
4. Generate charts as needed:
   `python tools/generate_chart.py <type> --data '<json>' --title "<title>"`
5. Less is more — cap at 3 total visuals (infographics + charts combined)

**Output:** `.tmp/infographics/*.png`, `.tmp/charts/*.png`

### Step 4: Assembly
1. Ensure user's logo is in the `Logo/` folder (PNG, JPG, or SVG)
2. Run: `python tools/render_newsletter.py --topic "<topic>"`
3. The script auto-detects logo, infographics, and charts from `.tmp/`
4. Open the output HTML in a browser to visually verify

**Output:** `.tmp/newsletter_YYYY-MM-DD.html`

### Step 5: Review & Send
1. Present the HTML file path to the user
2. Ask user to review and approve
3. On approval, send via Gmail:
   `python tools/send_gmail.py --html .tmp/newsletter_YYYY-MM-DD.html --to "<recipients>" --subject "<subject>"`
4. Use `--dry-run` flag first to verify recipients
5. Check `.tmp/send_report.json` for delivery status

**Output:** Emails sent + `.tmp/send_report.json`

---

## Error Handling

| Error | Action |
|-------|--------|
| Tavily rate limit | Wait 60s, retry once. If still failing, reduce to 2 queries |
| Claude API error | Retry once. If fails twice, output raw research for user review |
| Gemini image generation fails | Skip infographic, proceed with charts only. Not a blocker |
| No logo in Logo/ folder | Render without logo — header shows text only |
| Premailer CSS warning | Log but don't fail — expected with email HTML |
| Gmail auth expired | Delete token.json and re-authenticate |
| Recipient limit exceeded | Warn user about Gmail limits (500/day free, 2000/day Workspace) |

## Quality Checklist (verify before presenting to user)
- [ ] Subject line is compelling and under 50 characters
- [ ] Preview text hooks the reader and under 100 characters
- [ ] Every section cites at least one source
- [ ] No section exceeds 150 words
- [ ] At least one visual element (infographic or chart)
- [ ] Footer includes [UNSUBSCRIBE_LINK] placeholder
- [ ] Hebrew quality score >= 80
- [ ] No grammar or spelling issues flagged
- [ ] HTML renders correctly in browser (no broken images, no layout breaks)
- [ ] All outbound links have UTM parameters

## Clean Up Between Runs
Before generating a new newsletter, clear previous visuals:
```
rm .tmp/infographics/*.png .tmp/charts/*.png
```
Content files (search_results.json, newsletter_content.json) are overwritten automatically.

## Hebrew & RTL Notes
- All newsletter content is generated in Hebrew via the system prompt in `generate_content.py`
- The HTML template uses `dir="rtl"` and `lang="he"` for proper right-to-left rendering
- All fonts are set to Arial (with Arial Hebrew fallback) for consistent Hebrew display
- `stat-callout` uses `border-right` instead of `border-left` to align with RTL layout
- Infographic prompts are written in ENGLISH and request TEXT-FREE illustrations only (AI image models cannot render Hebrew/RTL correctly)
- Hebrew data visualization (stats, numbers) is done via HTML/CSS stat cards — never via AI-generated images
- Footer text is in Hebrew (unsubscribe, view in browser)
- Source links show "קראו עוד" instead of "Read more"

## Lessons Learned
- **AI image models cannot render Hebrew correctly** — Gemini, DALL-E, and others reverse RTL text. Solution: generate text-free illustrations only, and use HTML/CSS for any text overlays with correct RTL rendering.
