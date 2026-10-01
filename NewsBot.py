import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import feedparser
from datetime import datetime
import re
from html import escape
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv

load_dotenv()

# ========================================================================================
# ── AI PROVIDER SWITCH ──────────────────────────────────────────────────────────────────
# Set to "openai" or "anthropic"
LLM_PROVIDER = "openai"

# Model names (change here to upgrade/downgrade)
# OPENAI_MODEL    = "gpt-5.5"               # TEMP: trialling gpt-5.5 — better capability + token efficiency
OPENAI_MODEL = "gpt-5.6-terra"  # TEMP: trialling gpt-5.6 terra — better capability + token efficiency
# OPENAI_MODEL    = "gpt-5.6-luna"               # TEMP: trialling gpt-5.6 Luna — token efficiency
# OPENAI_MODEL  = "gpt-4o-mini"           # previous model — uncomment to revert (~40x cheaper)
ANTHROPIC_MODEL = (
    "claude-sonnet-4-6"  # alt: "claude-haiku-4-5-20251001", "claude-opus-4-6"
)

# Max output tokens per provider
# gpt-5.5 has improved token efficiency so real usage may be lower than gpt-4o-mini baseline (~1,800 tokens)
OPENAI_MAX_TOKENS = 8000
ANTHROPIC_MAX_TOKENS = (
    4500  # raised to accommodate KEY_NUMBERS block and enhanced prompts
)

if LLM_PROVIDER == "openai":
    from openai import OpenAI

    _key = os.environ.get("OPENAI_API_KEY")
    if not _key:
        raise EnvironmentError("OPENAI_API_KEY not found. Add it to your .env file.")
    client = OpenAI(api_key=_key)

elif LLM_PROVIDER == "anthropic":
    import anthropic as anthropic_sdk

    _key = os.environ.get("ANTHROPIC_API_KEY")
    if not _key:
        raise EnvironmentError("ANTHROPIC_API_KEY not found. Add it to your .env file.")
    client = anthropic_sdk.Anthropic(api_key=_key)

else:
    raise ValueError(
        f"Unknown LLM_PROVIDER: '{LLM_PROVIDER}'. Use 'openai' or 'anthropic'."
    )
# ────────────────────────────────────────────────────────────────────────────────────────

# Cost per token by model (input_rate, output_rate) — update when pricing changes
PRICING = {
    "gpt-5.6-luna": (0.20 / 1_000_000, 1.20 / 1_000_000),
    "gpt-5.6-terra": (2.00 / 1_000_000, 12.00 / 1_000_000),
    "gpt-5.5": (5.00 / 1_000_000, 30.00 / 1_000_000),
    "gpt-4o-mini": (0.15 / 1_000_000, 0.60 / 1_000_000),
    "gpt-4o": (2.50 / 1_000_000, 10.00 / 1_000_000),
    "claude-sonnet-4-6": (3.00 / 1_000_000, 15.00 / 1_000_000),
    "claude-haiku-4-5-20251001": (0.80 / 1_000_000, 4.00 / 1_000_000),
    "claude-opus-4-6": (15.0 / 1_000_000, 75.00 / 1_000_000),
}

# Known regulatory events to always surface in the EVENTS section.
# Keep this list current — the AI will drop past dates automatically via the prompt rule.
KNOWN_EVENTS = [
    {
        "date": "30 Sep 2026",
        "event": "UK cryptoasset authorisation gateway opens",
        "type": "reg",
        "url": "https://www.fca.org.uk/",
        "relevance": "High",
    },
    {
        "date": "Nov 2026",
        "event": "STEP2 DKK go-live (EBA Clearing)",
        "type": "infra",
        "url": "https://www.ebaclearing.eu/",
        "relevance": "High",
    },
    {
        "date": "1 Jan 2027",
        "event": "Basel 3.1 UK go-live",
        "type": "reg",
        "url": "https://www.bankofengland.co.uk/",
        "relevance": "High",
    },
    {
        "date": "25 Oct 2027",
        "event": "UK cryptoasset full regime enters force",
        "type": "reg",
        "url": "https://www.fca.org.uk/",
        "relevance": "High",
    },
]

RSS_FEEDS = {
    # ===== CENTRAL BANKS & REGULATORS =====
    "Bank of England - News": "https://www.bankofengland.co.uk/rss/news",
    "Bank of England - Publications": "https://www.bankofengland.co.uk/rss/publications",
    "Bank of England - Prudential Regulation": "https://www.bankofengland.co.uk/rss/prudential-regulation-publications",
    "FCA - News": "https://www.fca.org.uk/news/rss.xml",
    "HM Treasury": "https://www.gov.uk/government/organisations/hm-treasury.atom",
    "ECB - Press Releases": "https://www.ecb.europa.eu/rss/press.html",
    "European Banking Authority": "https://www.eba.europa.eu/rss.xml",
    "Financial Stability Board": "https://www.fsb.org/feed/",
    # ===== PAYMENTS INDUSTRY PUBLICATIONS =====
    "PaymentsSource": "https://www.americanbanker.com/feed?rss=true",
    "PYMNTS": "https://www.pymnts.com/feed/",
    "Finextra - Payments": "https://www.finextra.com/rss/channel.aspx?channel=payments",
    "The Payments Association": "https://www.thepaymentsassociation.org/feed/",
    "Payments Dive": "https://www.paymentsdive.com/feeds/news/",
    # ===== UK FINANCIAL SERVICES =====
    "UK Finance": "https://www.ukfinance.org.uk/rss.xml",
    # ===== INFRASTRUCTURE & NETWORKS =====
    "EBA Clearing": "https://www.ebaclearing.eu/feed/",
    # ===== GENERAL FINANCIAL NEWS =====
    "Financial Times - Payments": "https://www.ft.com/payments?format=rss",
    "Sky News - Business": "https://feeds.skynews.com/feeds/rss/business.xml",
}

# Inactive feeds (kept for reference):
# 'SWIFT':          'https://www.swift.com/news-events/rss'  — unstable, do not use
# 'Fintech Weekly': 'https://www.fintechweekly.com/feed/'    — low signal

articles_per_feed = 7

# ========================================================================================


def fetch_news():
    """
    Fetch news articles from all RSS feeds
    """

    print("\n" + "=" * 70)
    print("STEP 1: FETCHING NEWS FROM RSS FEEDS")
    print("=" * 70)

    allArticles = []

    for source_name, feed_url in RSS_FEEDS.items():
        try:
            print(f"\nFetching from {source_name}...")
            print(f"   URL: {feed_url}")

            # Use feedparser directly so sites that check the User-Agent (e.g. UK Finance)
            # receive feedparser's own UA rather than a bare requests UA.
            # Fall back to a requests pre-fetch only for SSL cert failures, where
            # feedparser's built-in urllib doesn't expose ssl_verify.
            feed = feedparser.parse(feed_url)
            if (
                feed.bozo
                and isinstance(getattr(feed, "bozo_exception", None), Exception)
                and "SSL" in str(feed.bozo_exception)
            ):
                print(f"   ⚠️  SSL cert error — retrying without verification")
                raw = requests.get(
                    feed_url,
                    timeout=20,
                    headers={"User-Agent": "Mozilla/5.0"},
                    verify=False,
                )
                feed = feedparser.parse(raw.content)

            # Check if feed loaded successfully
            if feed.bozo and not feed.entries:
                print(
                    f"   ⚠️  Warning: Feed may have issues ({getattr(feed, 'bozo_exception', '')})"
                )

            # Extract articles
            article_count = 0
            for entry in feed.entries[:articles_per_feed]:
                article = {
                    "source": source_name,
                    "title": entry.get("title", "No title"),
                    "link": entry.get("link", ""),
                    "published": entry.get("published", "No date"),
                    "summary": entry.get(
                        "summary", entry.get("description", "No summary")
                    ),
                }
                allArticles.append(article)
                article_count += 1

            print(f"   ✓ Got {article_count} articles")

        except Exception as e:
            print(f"   ✗ Error: {e}")
            continue

    print(f"\n{'='*70}")
    print(f"✓ TOTAL ARTICLES COLLECTED: {len(allArticles)}")
    print(f"{'='*70}")

    return allArticles


def fetch_press_page(url, source_name, max_items=5):
    headers = {"User-Agent": "PaymentsNewsBot/1.0"}
    r = requests.get(url, headers=headers, timeout=25)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    items = []

    # Very defensive parsing: headings + nearest text
    for h in soup.find_all(["h2", "h3"])[:max_items]:
        title = h.get_text(strip=True)
        if not title or len(title) < 8:
            continue

        link = None
        if h.find("a"):
            link = h.find("a").get("href")
            if link and link.startswith("/"):
                link = url.split("/")[0] + "//" + url.split("/")[2] + link

        summary = ""
        p = h.find_next("p")
        if p:
            summary = p.get_text(strip=True)

        items.append(
            {
                "source": source_name,
                "title": title,
                "link": link or url,
                "published": "Press release",
                "summary": summary,
                "region": "Global (UK/EMEA relevant)",
                "scheme": source_name,
            }
        )

    return items


def fetch_scheme_press():
    all_items = []

    schemes = [
        ("https://usa.visa.com/about-visa/newsroom/press-releases.html", "Visa"),
        ("https://www.mastercard.com/news/press/", "Mastercard"),
        ("https://www.swift.com/news-events/press-releases", "SWIFT"),
    ]

    for url, name in schemes:
        try:
            all_items += fetch_press_page(url, name, max_items=4)
            print(f"✓ Fetched {name} press releases")
        except Exception as e:
            print(f"⚠️  Skipped {name} press releases: {e}")

    return all_items


# ========================================================================================


def build_ai_input_document(articles):
    """Turn RSS articles into a compact, model-friendly document."""
    lines = []

    # Seed known regulatory events so the AI always surfaces them in the EVENTS block.
    # The prompt rule "future dates only" will drop any that have already passed.
    known_block = "[KNOWN_REGULATORY_EVENTS — always include future-dated entries in the EVENTS table]\n"
    for ev in KNOWN_EVENTS:
        known_block += f"Date: {ev['date']} | Event: {ev['event']} | Type: {ev['type']} | URL: {ev['url']} | Relevance: {ev['relevance']}\n"
    lines.append(known_block)

    for i, article in enumerate(articles, 1):
        # Clean summary (RSS summaries can be HTML)
        summary = re.sub(r"<[^>]+?>", "", article.get("summary", "")).strip()
        # Keep it bounded
        summary = summary[:3000]

        lines.append(
            f"[{i}]\n"
            f"Region: {article.get('region', 'Global')}\n"
            f"Scheme: {article.get('scheme', 'None')}\n"
            f"Source: {article.get('source')}\n"
            f"Title: {article.get('title')}\n"
            f"Published: {article.get('published')}\n"
            f"Link: {article.get('link')}\n"
            f"Summary: {summary}\n"
        )

    return "\n".join(lines)


# ========================================================================================


def extract_blocks(text: str) -> dict:
    blocks = {}
    pattern = re.compile(
        r"\[(?:BLOCK|BODY):(?P<name>[A-Z_]+)\]\s*(?P<body>.*?)\s*\[END\]", re.DOTALL
    )
    for m in pattern.finditer(text):
        blocks[m.group("name")] = m.group("body").strip()
    return blocks


def parse_stories(block_text: str) -> str:
    FONT = "font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;"
    TAG_INLINE = {
        "tag-risk": "background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;",
        "tag-regulatory": "background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;",
        "tag-tech": "background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0;",
        "tag-infra": "background:#fff7ed;color:#c2410c;border:1px solid #fed7aa;",
        "tag-macro": "background:#faf5ff;color:#7e22ce;border:1px solid #e9d5ff;",
        "tag-scheme": "background:#ecfdf5;color:#065f46;border:1px solid #a7f3d0;",
    }

    html_parts = []
    for chunk in block_text.strip().split("---"):
        chunk = chunk.strip()
        if not chunk:
            continue
        fields = {}
        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue
            if "|" in line and ":" in line:
                for part in line.split("|"):
                    part = part.strip()
                    if ":" in part:
                        k, _, v = part.partition(":")
                        fields[k.strip()] = v.strip()
            elif ":" in line:
                key, _, val = line.partition(":")
                fields[key.strip()] = val.strip()

        src_tag = fields.get("SRC", "")
        tag_raw = fields.get("TAG", "")
        label = fields.get("LABEL", "")
        head = fields.get("HEAD", "")
        why = fields.get("WHY", "")
        take = fields.get("TAKE", "")
        consult = fields.get("CONSULT", "")
        url = fields.get("URL", "#")
        scheme = fields.get("SCHEME", "")
        geo = fields.get("GEO", "")

        tag_style = TAG_INLINE.get(
            tag_raw, "background:#f3f4f6;color:#374151;border:1px solid #e5e7eb;"
        )

        extra_bullets = ""
        if scheme:
            extra_bullets += (
                f'<li style="margin:4px 0;font-size:13px;line-height:1.45;{FONT}">'
                f"<b>Scheme impact:</b> {escape(scheme)}</li>\n"
            )
        if geo:
            extra_bullets += (
                f'<li style="margin:4px 0;font-size:13px;line-height:1.45;{FONT}">'
                f"<b>UK/EMEA relevance:</b> {escape(geo)}</li>\n"
            )

        consult_li = (
            f'    <li style="margin:4px 0;font-size:13px;line-height:1.45;{FONT}"><b>Opportunity:</b> {escape(consult)}</li>\n'
            if consult
            else ""
        )

        html_parts.append(
            # Outer card — table replaces div.story so Outlook renders the border
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" class="story"'
            f' style="border:1px solid #d1d5db;border-radius:14px;margin-bottom:12px;background:#ffffff;">\n'
            f'<tr><td style="padding:14px;{FONT}">\n'
            # Kicker row — table replaces div.kicker (flex not supported in Outlook)
            f'  <table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation">\n'
            f'  <tr valign="middle">\n'
            f'    <td style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#4b5563;{FONT}">{escape(src_tag)}</td>\n'
            f'    <td align="right">'
            f'<span class="tag {escape(tag_raw)}" style="font-size:11px;font-weight:600;border-radius:999px;padding:4px 9px;{tag_style}{FONT}">'
            f"{escape(label)}</span></td>\n"
            f"  </tr>\n"
            f"  </table>\n"
            # Headline
            f'  <h3 style="margin:8px 0 6px;font-size:14px;color:#111827;{FONT}">{escape(head)}</h3>\n'
            # Bullets
            f'  <ul style="margin:10px 0 0;padding-left:18px;color:#374151;">\n'
            f'    <li style="margin:4px 0;font-size:13px;line-height:1.45;{FONT}"><b>Why it matters:</b> {escape(why)}</li>\n'
            f'    <li style="margin:4px 0;font-size:13px;line-height:1.45;{FONT}"><b>Key takeaway:</b> {escape(take)}</li>\n'
            f"{consult_li}"
            f"{extra_bullets}"
            f"  </ul>\n"
            # Filled blue button — renders as a proper CTA in Outlook
            f'  <a href="{url}" class="btn" style="display:inline-block;margin-top:10px;padding:8px 14px;border-radius:10px;'
            f'background:#2563eb;font-size:12px;color:#ffffff;font-weight:600;text-decoration:none;{FONT}"'
            f' aria-label="Read more: {escape(head)}">Read &#8594;</a>\n'
            f"</td></tr>\n"
            f"</table>"
        )
    return "\n".join(html_parts)


def parse_key_numbers(block_text: str) -> str:
    """Convert compact key-numbers format to an Outlook-compatible 4-cell table."""
    NUM_COLORS = {
        "kn-warn": "#c2410c",
        "kn-good": "#15803d",
        "kn-brand": "#2563eb",
    }
    cards = []
    for chunk in block_text.strip().split("---"):
        chunk = chunk.strip()
        if not chunk:
            continue
        fields = {}
        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue
            if "|" in line and ":" in line:
                for part in line.split("|"):
                    part = part.strip()
                    if ":" in part:
                        k, _, v = part.partition(":")
                        fields[k.strip()] = v.strip()
            elif ":" in line:
                key, _, val = line.partition(":")
                fields[key.strip()] = val.strip()

        val = escape(fields.get("VAL", "—"))
        label = escape(fields.get("LABEL", ""))
        src = escape(fields.get("SRC", ""))
        cls = fields.get("CLASS", "kn-brand")
        url = fields.get("URL", "#")
        num_color = NUM_COLORS.get(cls, "#2563eb")
        cards.append((val, label, src, num_color, url))

    while len(cards) < 4:
        cards.append(("—", "No data", "", "#2563eb", "#"))
    cards = cards[:4]

    tds = []
    for i, (val, label, src, num_color, url) in enumerate(cards):
        right_pad = "padding-right:12px;" if i < 3 else ""
        tds.append(
            f'<td width="25%" valign="top" height="1" style="{right_pad}">'
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" style="display:block;height:100%;background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;padding:14px 16px;text-decoration:none;color:inherit;box-sizing:border-box;">'
            f'<div style="font-size:24px;font-weight:800;color:{num_color};line-height:1;margin-bottom:3px;">{val}</div>'
            f'<div style="font-size:12px;color:#6b7280;line-height:1.3;">{label}</div>'
            f'<div style="font-size:10px;color:#6b7280;margin-top:5px;font-style:italic;">{src}</div>'
            f"</a>"
            f"</td>"
        )

    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation"><tr>'
        + "".join(tds)
        + "</tr></table>"
    )


def parse_focus(block: str) -> tuple[str, str]:
    # expects:
    # FOCUS_TITLE=...
    # FOCUS_SUBTITLE=...
    title = ""
    subtitle = ""
    for line in block.splitlines():
        line = line.strip()
        if line.startswith("FOCUS_TITLE="):
            title = line.split("=", 1)[1].strip()
        elif line.startswith("FOCUS_SUBTITLE="):
            subtitle = line.split("=", 1)[1].strip()
    return title, subtitle


def fill_template(template_html: str, mapping: dict) -> str:
    out = template_html
    for k, v in mapping.items():
        out = out.replace(f"{{{{{k}}}}}", v)
    return out


NEWSLETTER_PROMPT = """
    Be concise and information-dense. Do not over-explain.
    Collapse duplicate stories across sources into a single narrative.
    Prioritise by payments relevance, not recency. Surface second-order implications.

    Actively look for Visa, Mastercard, SWIFT scheme references even if the source is not the scheme itself.
    Scheme changes (rules, pricing, access, messaging standards) are always high priority.

    GEOGRAPHIC RULE (CRITICAL): Primary audience is UK and EMEA Payments professionals.
    Prioritise UK first, then EMEA. Include global items ONLY with clear UK/EMEA implications.
    Exclude US-only or APAC-only items unless they directly affect UK/EMEA firms
    (e.g. a US Fed rate decision with no BoE response or UK transmission mechanism should be excluded).

    Return ONLY the blocks below. No markdown. No HTML wrapper tags.

    [BLOCK:FOCUS]
    FOCUS_TITLE=max 8 words
    FOCUS_SUBTITLE=max 20 words
    [END]

    [BLOCK:KEY_NUMBERS]
    Exactly 4 cards. Prefer real numbers from the input. Where fewer than 4 exist, fill remaining
    cards with a regulatory deadline as a date metric (e.g. VAL="30 Sep", LABEL="FCA deadline").
    Never invent figures. URL must exist in the input document.
    CLASS: kn-warn=negative/risk, kn-good=positive/growth, kn-brand=neutral.
    Format — one card per block, separated by --- on its own line:
    VAL:VALUE|LABEL:short label|SRC:source name|CLASS:kn-[warn|good|brand]
    URL:https://...
    ---
    [END]

    [BLOCK:TOP_STORIES]
    4–5 stories. UK/EMEA only unless global item has direct UK/EMEA impact.
    Use compact format — Python renders the HTML:
    SRC:SOURCE|TAG:tag-[risk|regulatory|tech|infra|macro|scheme]|LABEL:TAG_TEXT
    HEAD:Headline — max 12 words
    WHY:Why it matters — max 18 words
    TAKE:Key takeaway — max 18 words
    CONSULT:Specific consulting workstream this creates — max 18 words (omit line entirely if no genuine angle exists)
    URL:https://...
    SCHEME:Scheme impact (optional — only for scheme stories)
    GEO:UK/EMEA relevance (optional — only for global stories)
    ---
    [END]

    [BLOCK:RISK]
    2–3 stories. UK regulators (FCA, PRA, BoE) and EU first. Same compact format as TOP_STORIES.
    [END]

    [BLOCK:MACRO]
    1–2 stories. Global macro only where UK/EMEA payments firms are directly affected. Same compact format.
    [END]

    [BLOCK:EVENTS]
    <table> with <thead> and <tbody>. Columns: Date | Event | Type | Relevance.
    Add scope="col" to every <th>. Type badge: <span class="ev-badge ev-[reg|comp|infra|scheme]">Label</span>
    Relevance: High / Medium / Watch. Max 6 rows, future dates only (today is {TODAY}). Input-only.
    Wrap the event name in <a href="URL"> using the source URL from the input document where available.
    If none: <div class="muted">No upcoming events detected.</div>
    [END]

    [BLOCK:TAKEAWAYS]
    4 cards in a two-column Outlook-safe table. Max 20 words each. One sentence only.
    Labels: Risk signal | Regulatory deadline | Tech opportunity | Scheme change | Consulting demand | Macro watch
    Type colour map — inline styles are required; Outlook strips CSS class-based styles:
      default:     border:#2563eb  bg:#f8faff  label-color:#2563eb
      mini-risk:   border:#b91c1c  bg:#fef9f9  label-color:#b91c1c
      mini-tech:   border:#15803d  bg:#f6fef8  label-color:#15803d
      mini-macro:  border:#7e22ce  bg:#fdf8ff  label-color:#7e22ce
      mini-scheme: border:#065f46  bg:#f0fdfb  label-color:#065f46
    Replace [BORDER], [BG], [LABEL-COLOR], [TYPE], [LABEL], [TEXT] with real values:
    <table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation"><tr valign="top">
    <td width="50%" style="padding-right:5px;"><div class="mini mini-[TYPE]" style="border-left:4px solid [BORDER];border-radius:0 12px 12px 0;padding:10px 12px;background:[BG];"><div class="mini-label" style="font-size:12px;font-weight:700;color:[LABEL-COLOR];text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px;font-family:Arial,sans-serif;">[LABEL]</div><p style="margin:0;font-size:12px;color:#111827;line-height:1.4;font-family:Arial,sans-serif;">[TEXT]</p></div></td>
    <td width="50%" style="padding-left:5px;"><div class="mini mini-[TYPE]" style="border-left:4px solid [BORDER];border-radius:0 12px 12px 0;padding:10px 12px;background:[BG];"><div class="mini-label" style="font-size:12px;font-weight:700;color:[LABEL-COLOR];text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px;font-family:Arial,sans-serif;">[LABEL]</div><p style="margin:0;font-size:12px;color:#111827;line-height:1.4;font-family:Arial,sans-serif;">[TEXT]</p></div></td>
    </tr><tr valign="top">
    <td style="padding-right:5px;padding-top:10px;"><div class="mini mini-[TYPE]" style="border-left:4px solid [BORDER];border-radius:0 12px 12px 0;padding:10px 12px;background:[BG];"><div class="mini-label" style="font-size:12px;font-weight:700;color:[LABEL-COLOR];text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px;font-family:Arial,sans-serif;">[LABEL]</div><p style="margin:0;font-size:12px;color:#111827;line-height:1.4;font-family:Arial,sans-serif;">[TEXT]</p></div></td>
    <td style="padding-left:5px;padding-top:10px;"><div class="mini mini-[TYPE]" style="border-left:4px solid [BORDER];border-radius:0 12px 12px 0;padding:10px 12px;background:[BG];"><div class="mini-label" style="font-size:12px;font-weight:700;color:[LABEL-COLOR];text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px;font-family:Arial,sans-serif;">[LABEL]</div><p style="margin:0;font-size:12px;color:#111827;line-height:1.4;font-family:Arial,sans-serif;">[TEXT]</p></div></td>
    </tr></table>
    [END]

    [BLOCK:QUICK_LINKS]
    6–8 links covering both high-signal payments items and any lower-relevance items worth noting.
    <a href="URL">TITLE</a>
    [END]

    Rules:
    - URLs must exist in the input document. Do not invent links.
    - FOCUS_TITLE: max 8 words. FOCUS_SUBTITLE: max 20 words.
    Tag classes: tag-risk=fraud/crime/cyber | tag-regulatory=FCA/PRA/BoE/EU | tag-tech=ISO20022/rails/AI/cloud | tag-infra=RTGS/CHAPS/network | tag-macro=rates/M&A/macro | tag-scheme=Visa/MC/SWIFT/SEPA/FPS
    """


def generate_newsletter_html(client, articles, template_path="TEMPLATE.html"):
    document = build_ai_input_document(articles)
    today_str = datetime.now().strftime("%d %b %Y")
    prompt = NEWSLETTER_PROMPT.replace("{TODAY}", today_str)

    # ── CALL SELECTED PROVIDER ──────────────────────────────────────────────
    if LLM_PROVIDER == "openai":
        resp = client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": "You are an expert payments news editor producing HTML fragments for a fixed email template.",
                },
                {
                    "role": "user",
                    "content": prompt
                    + "\n\n---BEGIN DOCUMENT---\n"
                    + document
                    + "\n---END DOCUMENT---",
                },
            ],
            max_output_tokens=OPENAI_MAX_TOKENS,
        )
        ai_text = resp.output_text
        usage = getattr(resp, "usage", None)
        input_tokens = (
            getattr(usage, "input_tokens", None) if usage is not None else None
        )
        output_tokens = (
            getattr(usage, "output_tokens", None) if usage is not None else None
        )
        model_used = resp.model
        provider_label = f"OpenAI · {model_used}"

    elif LLM_PROVIDER == "anthropic":
        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=ANTHROPIC_MAX_TOKENS,
            system="You are an expert payments news editor producing HTML fragments for a fixed email template.",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                    + "\n\n---BEGIN DOCUMENT---\n"
                    + document
                    + "\n---END DOCUMENT---",
                }
            ],
        )
        ai_text = resp.content[0].text
        input_tokens = resp.usage.input_tokens
        output_tokens = resp.usage.output_tokens
        model_used = resp.model
        provider_label = f"Anthropic · {model_used}"

    # ── TOKEN USAGE + COST ───────────────────────────────────────────────────
    print(
        {
            "model": model_used,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
    )

    if input_tokens is not None and output_tokens is not None:
        for key, (in_rate, out_rate) in PRICING.items():
            if key in model_used:
                cost = input_tokens * in_rate + output_tokens * out_rate
                print(f"Cost (estimated): ${cost:.6f}")
                break

    blocks = extract_blocks(ai_text)

    focus_title, focus_subtitle = parse_focus(blocks.get("FOCUS", ""))
    if not focus_title:
        focus_title = "Payments signals"
    if not focus_subtitle:
        focus_subtitle = "Regulation • Risk • Rails"

    today = datetime.now().strftime("%d %b %Y")
    date_line = f"{today} • {len(articles)} items scanned"

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    mapping = {
        "TITLE": "Payments Industry Newsletter",
        "DATE_LINE": escape(date_line),
        "FOCUS_TITLE": escape(focus_title),
        "FOCUS_SUBTITLE": escape(focus_subtitle),
        "KEY_NUMBERS": parse_key_numbers(blocks.get("KEY_NUMBERS", "")),
        "TOP_STORIES": parse_stories(blocks.get("TOP_STORIES", "")),
        "RISK": parse_stories(blocks.get("RISK", "")),
        "MACRO": parse_stories(blocks.get("MACRO", "")),
        "EVENTS": blocks.get(
            "EVENTS", '<div class="muted">No upcoming events detected.</div>'
        ),
        "TAKEAWAYS": blocks.get("TAKEAWAYS", ""),
        "QUICK_LINKS": blocks.get("QUICK_LINKS", ""),
        "AI_PROVIDER": escape(provider_label),
        "AUTHORS": AUTHOR_SECTION_HTML,
        "MAX_WIDTH": "1080",
        "FOOTER_NOTE": escape("Payments News • Auto-generated")
        + f' &nbsp;|&nbsp; <span style="font-style:italic;">Generated by {provider_label}</span>',
    }

    return fill_template(template, mapping), blocks, provider_label


# ========================================================================================
# ── OUTLOOK EMAIL OUTPUT ────────────────────────────────────────────────────────────────
# Added by Morgan Moloney — Outlook-compatible email rendering.
# generate_outlook_email_html() reuses the AI blocks from generate_newsletter_html()
# (no second API call) and injects the author section below.
# Replace [Job Title] placeholders before sending.
# ========================================================================================

AUTHOR_SECTION_HTML = """
<table width="100%" cellpadding="22" cellspacing="0" border="0" bgcolor="#ffffff"
  style="background:#ffffff;border:1px solid #d1d5db;border-radius:16px;" role="presentation">
  <tr><td style="font-family:Arial,Helvetica,sans-serif;">
    <div style="font-size:16px;font-weight:700;padding-bottom:10px;border-bottom:1px solid #e5e7eb;color:#111827;margin-bottom:16px;">Your curators</div>
    <table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation">
      <tr valign="middle">

        <!-- Liam Grimwood -->
        <td width="50%" style="padding-right:16px;">
          <table cellpadding="0" cellspacing="0" border="0" role="presentation">
            <tr valign="middle">
              <td width="64" style="padding-right:12px;">
                <!--[if !mso]><!-->
                <img src="data:image/jpeg;base64,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" width="52" height="52" alt="Liam Grimwood" style="border-radius:50%;display:block;">
                <!--<![endif]-->
                <!--[if mso]><table cellpadding="0" cellspacing="0" border="0" width="52" height="52"><tr><td width="52" height="52" align="center" valign="middle" bgcolor="#3A0CA3" style="font-size:18px;font-weight:700;color:#ffffff;font-family:Arial,sans-serif;">LG</td></tr></table><![endif]-->
              </td>
              <td>
                <div style="font-size:14px;font-weight:700;color:#111827;font-family:Arial,Helvetica,sans-serif;">Liam Grimwood</div>
              </td>
            </tr>
          </table>
        </td>

        <!-- Morgan Moloney -->
        <td width="50%">
          <table cellpadding="0" cellspacing="0" border="0" role="presentation">
            <tr valign="middle">
              <td width="64" style="padding-right:12px;">
                <!--[if !mso]><!-->
                <img src="data:image/jpeg;base64,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" width="52" height="52" alt="Morgan Moloney" style="border-radius:50%;display:block;">
                <!--<![endif]-->
                <!--[if mso]><table cellpadding="0" cellspacing="0" border="0" width="52" height="52"><tr><td width="52" height="52" align="center" valign="middle" bgcolor="#7F16FF" style="font-size:18px;font-weight:700;color:#ffffff;font-family:Arial,sans-serif;">MM</td></tr></table><![endif]-->
              </td>
              <td>
                <div style="font-size:14px;font-weight:700;color:#111827;font-family:Arial,Helvetica,sans-serif;">Morgan Moloney</div>
              </td>
            </tr>
          </table>
        </td>

      </tr>
    </table>
  </td></tr>
</table>
"""


def generate_outlook_email_html(
    blocks: dict,
    articles: list,
    provider_label: str,
    template_path: str = "TEMPLATE.html",
) -> str:
    """
    Renders an Outlook-compatible email from pre-computed AI blocks.
    Call this after generate_newsletter_html() — it reuses the same blocks
    so no second API call is made.
    """
    focus_title, focus_subtitle = parse_focus(blocks.get("FOCUS", ""))
    if not focus_title:
        focus_title = "Payments signals"
    if not focus_subtitle:
        focus_subtitle = "Regulation • Risk • Rails"

    today = datetime.now().strftime("%d %b %Y")
    date_line = f"{today} • {len(articles)} items scanned"

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    mapping = {
        "TITLE": "Payments Industry Newsletter",
        "DATE_LINE": escape(date_line),
        "FOCUS_TITLE": escape(focus_title),
        "FOCUS_SUBTITLE": escape(focus_subtitle),
        "KEY_NUMBERS": parse_key_numbers(blocks.get("KEY_NUMBERS", "")),
        "TOP_STORIES": parse_stories(blocks.get("TOP_STORIES", "")),
        "RISK": parse_stories(blocks.get("RISK", "")),
        "MACRO": parse_stories(blocks.get("MACRO", "")),
        "EVENTS": blocks.get(
            "EVENTS", '<div class="muted">No upcoming events detected.</div>'
        ),
        "TAKEAWAYS": blocks.get("TAKEAWAYS", ""),
        "QUICK_LINKS": blocks.get("QUICK_LINKS", ""),
        "AI_PROVIDER": escape(provider_label),
        "AUTHORS": AUTHOR_SECTION_HTML,
        "MAX_WIDTH": "680",
        "FOOTER_NOTE": escape("Payments News • Auto-generated")
        + f' &nbsp;|&nbsp; <span style="font-style:italic;">Generated by {escape(provider_label)}</span>',
    }

    return fill_template(template, mapping)


# ────────────────────────────────────────────────────────────────────────────────────────


# ========================================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("     PAYMENTS NEWS BOT")
    print("=" * 70)

    # Step 1: Fetch news
    articles = fetch_news()  # your RSS feeds
    scheme_articles = fetch_scheme_press()

    articles.extend(scheme_articles)

    if not articles:
        print("\n❌ No articles found!")
    else:
        # Step 2: Generate browser preview (also runs the AI call)
        browser_html, ai_blocks, provider_label = generate_newsletter_html(
            client, articles, template_path="TEMPLATE.html"
        )

        # Step 3: Generate Outlook email (reuses AI blocks — no second API call)
        outlook_html = generate_outlook_email_html(
            ai_blocks, articles, provider_label, template_path="TEMPLATE.html"
        )

        # Save both outputs
        output_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "GeneratedReports"
        )
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%d-%m-%y_%H-%M")

        browser_file = f"PaymentsNewsReport_{timestamp}.html"
        with open(os.path.join(output_dir, browser_file), "w", encoding="utf-8") as f:
            f.write(browser_html)

        email_file = f"PaymentsEmail_{timestamp}.html"
        with open(os.path.join(output_dir, email_file), "w", encoding="utf-8") as f:
            f.write(outlook_html)

        print(f"\n💾 Browser preview : GeneratedReports/{browser_file}")
        print(f"📧 Outlook email   : GeneratedReports/{email_file}")
        print(
            f"   Open the browser file to check layout; use the email file for sending."
        )

        print("\n✅ SUCCESS!")


# TO DO:
# Tailor the number of reports to pull from each place based on their priority and gain
# Attach as an email
# Lambda
# Store arrays on S3 buckets
