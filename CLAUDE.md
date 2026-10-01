# PymntNewsBot — Claude Context

## Project Overview

An automated **payments industry newsletter generator** for UK/EMEA audiences. It:
1. Aggregates articles from RSS feeds (regulators, industry publications, financial news)
2. Scrapes press releases directly from payment scheme websites (Visa, etc.)
3. Sends the full article list to an LLM (OpenAI or Anthropic) for curation and summarisation
4. Fills an HTML email template with the AI-generated content
5. Saves two outputs: a browser preview and an Outlook-compatible email HTML

Target audience: UK/EMEA payments industry professionals and leaders.
Curators: Liam Grimwood + Morgan Moloney (Manchester Payments Team).

---

## File Structure

| File | Purpose |
|------|---------|
| `NewsBot.py` | Single-file application — all logic lives here |
| `TEMPLATE.html` | HTML email template using `{{VARIABLE}}` placeholders — single source of truth for both outputs |
| `requirements.txt` | Python dependencies for local install and GitHub Actions CI |
| `.github/workflows/newsletter.yml` | GitHub Actions weekly schedule (Monday 07:00 UTC) |
| `GeneratedReports/` | Timestamped output files written by NewsBot.py each run |
| `Archived/` | Old versions of the script — not used |

---

## Key Configuration (in NewsBot.py)

- **`LLM_PROVIDER`** (line ~18): `"openai"` or `"anthropic"` — controls which API is called.
- **`OPENAI_MODEL`** (line ~22): Currently `gpt-5.6-terra`. Change here to switch model.
- **`ANTHROPIC_MODEL`** (line ~25): Currently `claude-sonnet-4-6`.
- **`RSS_FEEDS`** (lines ~55–85): Dictionary of source name → RSS URL. Covers BoE, FCA, PYMNTS, Payments Dive, UK Finance, FT, Sky News, NilsonReport, etc.
- **`articlesCountPerFeed`**: Articles fetched per feed (default: 7).
- **`schemes`**: Payment scheme press release page URLs. Only Visa is active; Mastercard/SWIFT are commented out.
- **`NEWSLETTER_PROMPT`**: Large system prompt defining newsletter structure, section rules, geographic filters, and word/length constraints.
- **`OPENAI_MAX_TOKENS`**: Token cap for OpenAI response (default: 8000).

---

## Core Logic Flow

```
python NewsBot.py
  ├── fetch_news()                    → parse RSS feeds via feedparser
  ├── fetch_scheme_press()            → scrape Visa press release HTML page
  ├── build_ai_input_document()       → format articles as structured text for AI
  ├── generate_newsletter_html_with_gpt()
  │     ├── LLM API call (OpenAI or Anthropic)
  │     ├── extract_blocks()          → parse [BLOCK:NAME]...[END] from AI output
  │     ├── parse_focus()             → extract FOCUS_TITLE + FOCUS_SUBTITLE
  │     ├── fill_template()           → replace {{VARS}} in TEMPLATE.html
  │     └── generate_outlook_email_html() → second pass for email-specific rendering
  └── Write to GeneratedReports/
        ├── PaymentsNewsReport_DD-MM-YY_HH-MM.html       (browser preview)
        └── PaymentsNewsReport_DD-MM-YY_HH-MM_email.html (Outlook email)
```

---

## TEMPLATE.html Layout

Two-column layout (60% left / 40% right) using table-based HTML for Outlook compatibility:

- **Left column**: Top Stories
- **Right column**: Events → Takeaways → Risk → Macro → Further Reading
  - Further Reading has `flex:1` (CSS) so it stretches to match the left column height — works in browsers; Outlook falls back to natural stacking
- **Full width below columns**: Authors section (Liam Grimwood + Morgan Moloney), Footer

Hero header shows title, date, focus story, and key stat pills. AI provider label is intentionally omitted from the header.

---

## Newsletter Sections (AI-generated)

| Block | Content |
|-------|---------|
| `FOCUS` | Single headline story (title + subtitle) |
| `KEY_NUMBERS` | 3–4 stat pills (e.g. transaction volumes, fines) |
| `TOP_STORIES` | 3–5 curated articles with bullets |
| `RISK` | Regulatory/compliance stories |
| `MACRO` | Macro-economic signals relevant to payments |
| `EVENTS` | Upcoming industry events table |
| `TAKEAWAYS` | Executive summary bullets |
| `QUICK_LINKS` | Short-form links to additional stories |

---

## Dependencies

```
feedparser       # RSS parsing
openai           # OpenAI API client
anthropic        # Anthropic API client
requests         # HTTP for press release scraping
beautifulsoup4   # HTML parsing for press pages
```

---

## Environment Variables

| Variable | Required for |
|----------|-------------|
| `OPENAI_API_KEY` | `LLM_PROVIDER = "openai"` |
| `ANTHROPIC_API_KEY` | `LLM_PROVIDER = "anthropic"` |

For GitHub Actions: add the relevant key as a repository secret under `liamaccenture/PaymentsDigestAI` → Settings → Secrets → Actions.

---

## Running the Bot

```bash
python NewsBot.py
```

Outputs two files in `GeneratedReports/`. Open the browser file to check layout; use the email file for sending.

---

## GitHub Actions Schedule

Workflow at `.github/workflows/newsletter.yml` runs every **Monday at 07:00 UTC** (08:00 UK / 09:00 CEST). Can also be triggered manually from the GitHub Actions tab. Generated HTML files are uploaded as artifacts (retained 30 days).

Email delivery (task 6) is not yet wired up — for now, download artifacts from the Actions run.

---

## Known Issues / TODOs

1. **Email sending**: `smtplib` is imported but not implemented. Next task — configure SMTP delivery to Liam and Morgan first, then wider distribution list.
2. **Mastercard/SWIFT press pages**: Commented out in `schemes` list — to be re-enabled.
3. **Outlook column alignment**: CSS flexbox aligns column bottoms in browsers; Outlook renders natural table stacking (right column may end slightly shorter than left — acceptable).
