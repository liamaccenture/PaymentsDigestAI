# PymntNewsBot — Claude Context

## Project Overview

An automated **payments industry newsletter generator** for UK/EMEA audiences. It:
1. Aggregates articles from RSS feeds (regulators, industry publications, financial news)
2. Scrapes press releases directly from payment scheme websites (Visa, etc.)
3. Sends the full article list to OpenAI (GPT-4o-mini) for curation and summarisation
4. Fills an HTML email template with the AI-generated content
5. Saves the final newsletter as a timestamped HTML file

Target audience: UK/EMEA payments industry professionals and leaders.

---

## File Structure

| File | Purpose |
|------|---------|
| `NewsBot.py` | Single-file application — all logic lives here |
| `TEMPLATE.html` | HTML email template using `{{VARIABLE}}` placeholders |
| `PaymentsNewsletterExample.html` | Sample generated output (reference only) |
| `Archived/` | Old versions of the script — not used |

---

## Key Configuration (in NewsBot.py)

- **`RSS_FEEDS`** (lines ~20–51): Dictionary of source name → RSS URL. Covers BoE, FCA, PYMNTS, Payments Dive, UK Finance, FT, Sky News, NilsonReport, etc.
- **`articlesCountPerFeed`** (line ~53): Articles fetched per feed (default: 7).
- **`schemes`** (lines ~148–152): Payment scheme press release page URLs. Only Visa is active; Mastercard/SWIFT are commented out.
- **`NEWSLETTER_PROMPT`** (lines ~221–332): Large system prompt defining newsletter structure, section rules, geographic filters, and word/length constraints.
- **`max_output_tokens`** (line ~344): Token cap for GPT response (default: 5500).

---

## Core Logic Flow

```
python NewsBot.py
  ├── fetch_news()              → parse RSS feeds via feedparser
  ├── fetch_scheme_press()      → scrape Visa press release HTML page
  ├── build_ai_input_document() → format articles as structured text for AI
  ├── generate_newsletter_html_with_gpt()
  │     ├── OpenAI Responses API call (gpt-4o-mini)
  │     ├── extract_blocks()    → parse [BLOCK:NAME]...[END] from AI output
  │     ├── parse_focus()       → extract FOCUS_TITLE + FOCUS_SUBTITLE
  │     └── fill_template()     → replace {{VARS}} in TEMPLATE.html
  └── Write email_preview_YYYYMMDD_HHMMSS.html
```

---

## Newsletter Sections (AI-generated)

The AI prompt instructs GPT to produce these named blocks:

| Block | Content |
|-------|---------|
| `FOCUS` | Single headline story (title + subtitle) |
| `PILLS` | Short badge-style callouts (scheme impacts, regulatory alerts) |
| `TOP_STORIES` | 3–5 curated articles with bullets |
| `RISK` | Regulatory/compliance stories |
| `MACRO` | Macro-economic signals relevant to payments |
| `EVENTS` | Upcoming industry events |
| `TAKEAWAYS` | Executive summary bullets |
| `QUICK_LINKS` | Short-form links to additional stories |
| `OUTSIDE` | Non-payments adjacent stories worth noting |

---

## Dependencies

```
feedparser       # RSS parsing
openai           # OpenAI API client
requests         # HTTP for press release scraping
beautifulsoup4   # HTML parsing for press pages
```

Standard library: `re`, `html`, `datetime`, `smtplib`, `email.mime` (last two unused in current MVP).

---

## Known Issues / TODOs

1. **Email sending**: `smtplib` is imported but not implemented. Planned next step.
2. **AWS Lambda deployment**: Flagged in comments as a future goal, along with S3 article caching.
3. **Mastercard/SWIFT press pages**: Commented out in `schemes` list — to be re-enabled.

---

## Running the Bot

```bash
python NewsBot.py
```

Outputs a file like `email_preview_20260427_143000.html` in the working directory.

---

## Cost Tracking

The script calculates and prints API cost after each run using gpt-4o-mini pricing:
- Input: $0.15 / 1M tokens
- Output: $0.60 / 1M tokens
