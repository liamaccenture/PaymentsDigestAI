import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import feedparser
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
OPENAI_MODEL    = "gpt-5.6-terra"               # TEMP: trialling gpt-5.6 terra — better capability + token efficiency
# OPENAI_MODEL    = "gpt-5.6-luna"               # TEMP: trialling gpt-5.6 Luna — token efficiency
# OPENAI_MODEL  = "gpt-4o-mini"           # previous model — uncomment to revert (~40x cheaper)
ANTHROPIC_MODEL = "claude-sonnet-4-6"     # alt: "claude-haiku-4-5-20251001", "claude-opus-4-6"

# Max output tokens per provider
# gpt-5.5 has improved token efficiency so real usage may be lower than gpt-4o-mini baseline (~1,800 tokens)
OPENAI_MAX_TOKENS    = 8000
ANTHROPIC_MAX_TOKENS = 4500   # raised to accommodate KEY_NUMBERS block and enhanced prompts

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
    raise ValueError(f"Unknown LLM_PROVIDER: '{LLM_PROVIDER}'. Use 'openai' or 'anthropic'.")
# ────────────────────────────────────────────────────────────────────────────────────────

RSS_FEEDS = {
    # 'SWIFT': 'https://www.swift.com/news-events/rss'

    # ===== CENTRAL BANKS & REGULATORS =====
    'Bank of England - News': 'https://www.bankofengland.co.uk/rss/news',
    'Bank of England - Publications': 'https://www.bankofengland.co.uk/rss/publications',
    'Bank of England - Prudential Regulation': 'https://www.bankofengland.co.uk/rss/prudential-regulation-publications',
    'FCA - News': 'https://www.fca.org.uk/news/rss.xml',
    'HM Treasury': 'https://www.gov.uk/government/organisations/hm-treasury.atom',
    'ECB - Press Releases': 'https://www.ecb.europa.eu/rss/press.html',
    'European Banking Authority': 'https://www.eba.europa.eu/rss.xml',
    'Financial Stability Board': 'https://www.fsb.org/feed/',
    # 'SWIFT': 'https://www.swift.com/news-events/news' # Do not use

    # ===== PAYMENTS INDUSTRY PUBLICATIONS =====
    'PaymentsSource': 'https://www.americanbanker.com/feed?rss=true',
    'PYMNTS': 'https://www.pymnts.com/feed/',
    'Finextra - Payments': 'https://www.finextra.com/rss/channel.aspx?channel=payments',
    'The Payments Association': 'https://www.thepaymentsassociation.org/feed/',
    # 'Finextra': 'https://www.finextra.com/rss/payments.aspx',
    'Payments Dive': 'https://www.paymentsdive.com/feeds/news/',
    # 'Fintech Weekly': 'https://www.fintechweekly.com/feed/',

    # ===== UK FINANCIAL SERVICES =====
    'UK Finance': 'https://www.ukfinance.org.uk/rss.xml',

    # ===== INFRASTRUCTURE & NETWORKS =====
    'EBA Clearing': 'https://www.ebaclearing.eu/feed/',

    # ===== GENERAL FINANCIAL NEWS =====
    'Financial Times - Payments': 'https://www.ft.com/payments?format=rss',
    'Sky News - Business': 'https://feeds.skynews.com/feeds/rss/business.xml',

}

articlesCountPerFeed = 7

# ========================================================================================

def fetch_news():
    """
    Fetch news articles from all RSS feeds
    """

    print("\n" + "="*70)
    print("STEP 1: FETCHING NEWS FROM RSS FEEDS")
    print("="*70)

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
            if feed.bozo and isinstance(getattr(feed, 'bozo_exception', None), Exception) and 'SSL' in str(feed.bozo_exception):
                print(f"   ⚠️  SSL cert error — retrying without verification")
                raw = requests.get(
                    feed_url, timeout=20,
                    headers={"User-Agent": "Mozilla/5.0"},
                    verify=False
                )
                feed = feedparser.parse(raw.content)

            # Check if feed loaded successfully
            if feed.bozo and not feed.entries:
                print(f"   ⚠️  Warning: Feed may have issues ({getattr(feed, 'bozo_exception', '')})")
            
            # Extract articles
            article_count = 0
            for entry in feed.entries[:articlesCountPerFeed]:
                article = {
                    'source': source_name,
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.get('published', 'No date'),
                    'summary': entry.get('summary', entry.get('description', 'No summary'))
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
    headers = {
        "User-Agent": "PaymentsNewsBot/1.0"
    }
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

        items.append({
            "source": source_name,
            "title": title,
            "link": link or url,
            "published": "Press release",
            "summary": summary,
            "region": "Global (UK/EMEA relevant)",
            "scheme": source_name
        })

    return items

def fetch_scheme_press():
    all_items = []

    schemes = [
        ("https://usa.visa.com/about-visa/newsroom/press-releases.html", "Visa"),
        # ("https://www.mastercard.com/news/press/", "Mastercard"),
        # ("https://www.swift.com/news-events/press-releases", "SWIFT"),
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

    for i, article in enumerate(articles, 1):
        # Clean summary (RSS summaries can be HTML)
        summary = re.sub(r'<[^>]+?>', '', article.get("summary", "")).strip()
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
        r"\[(?:BLOCK|BODY):(?P<name>[A-Z_]+)\]\s*(?P<body>.*?)\s*\[END\]",
        re.DOTALL
    )
    for m in pattern.finditer(text):
        blocks[m.group("name")] = m.group("body").strip()
    return blocks

def parse_stories(block_text: str) -> str:
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
            # Handle pipe-separated pairs on one line: SRC:X|TAG:Y|LABEL:Z
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
        label   = fields.get("LABEL", "")
        head    = fields.get("HEAD", "")
        why     = fields.get("WHY", "")
        take    = fields.get("TAKE", "")
        consult = fields.get("CONSULT", "")
        url     = fields.get("URL", "#")
        scheme  = fields.get("SCHEME", "")
        geo     = fields.get("GEO", "")

        extra_bullets = ""
        if scheme:
            extra_bullets += f'<li><b>Scheme impact:</b> {escape(scheme)}</li>\n'
        if geo:
            extra_bullets += f'<li><b>UK/EMEA relevance:</b> {escape(geo)}</li>\n'

        html_parts.append(
            f'<div class="story">\n'
            f'<div class="kicker"><div class="src">{escape(src_tag)}</div>'
            f'<span class="tag {escape(tag_raw)}">{escape(label)}</span></div>\n'
            f'<h3>{escape(head)}</h3>\n'
            f'<ul class="bullets">\n'
            f'<li><b>Why it matters:</b> {escape(why)}</li>\n'
            f'<li><b>Key takeaway:</b> {escape(take)}</li>\n'
            f'<li><b>Opportunity:</b> {escape(consult)}</li>\n'
            f'{extra_bullets}'
            f'</ul>\n'
            f'<a class="btn" href="{url}" aria-label="Read more: {escape(head)}">Read →</a>\n'
            f'</div>'
        )
    return "\n".join(html_parts)

def parse_key_numbers(block_text: str) -> str:
    """Convert compact key-numbers format to an Outlook-compatible 4-cell table."""
    NUM_COLORS = {
        "kn-warn":  "#c2410c",
        "kn-good":  "#15803d",
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

        val       = escape(fields.get("VAL", "—"))
        label     = escape(fields.get("LABEL", ""))
        src       = escape(fields.get("SRC", ""))
        cls       = fields.get("CLASS", "kn-brand")
        url       = fields.get("URL", "#")
        num_color = NUM_COLORS.get(cls, "#2563eb")
        cards.append((val, label, src, num_color, url))

    while len(cards) < 4:
        cards.append(("—", "No data", "", "#2563eb", "#"))
    cards = cards[:4]

    tds = []
    for i, (val, label, src, num_color, url) in enumerate(cards):
        right_pad = "padding-right:12px;" if i < 3 else ""
        tds.append(
            f'<td width="25%" valign="top" style="{right_pad}">'
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" style="display:block;background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;padding:14px 16px;text-decoration:none;color:inherit;">'
            f'<div style="font-size:24px;font-weight:800;color:{num_color};line-height:1;margin-bottom:3px;">{val}</div>'
            f'<div style="font-size:12px;color:#6b7280;line-height:1.3;">{label}</div>'
            f'<div style="font-size:10px;color:#6b7280;margin-top:5px;font-style:italic;">{src}</div>'
            f'</a>'
            f'</td>'
        )

    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation"><tr>'
        + "".join(tds)
        + '</tr></table>'
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
    Exclude US-only or APAC-only items unless they directly affect UK/EMEA firms.

    Return ONLY the blocks below. No markdown. No HTML wrapper tags.

    [BLOCK:FOCUS]
    FOCUS_TITLE=max 8 words
    FOCUS_SUBTITLE=max 20 words
    [END]

    [BLOCK:KEY_NUMBERS]
    Exactly 4 cards. Use real numbers from input only — no invented figures.
    Fill gaps with regulatory deadlines as date metrics (e.g. VAL="18 May", LABEL="FCA deadline").
    CLASS: kn-warn=negative/risk, kn-good=positive/growth, kn-brand=neutral.
    URL must exist in the input document.
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
    CONSULT:Specific consulting workstream this creates — max 18 words
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
    4 cards in a two-column grid. Max 20 words each. One sentence only.
    Labels: Risk signal | Regulatory deadline | Tech opportunity | Scheme change | Consulting demand | Macro watch
    Modifier class: mini-risk | mini-tech | mini-macro | mini-scheme (omit for default blue).
    Format — use a 2-column table (Outlook-safe), 2 cards per row:
    <table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation"><tr valign="top">
    <td width="50%" style="padding-right:5px;"><div class="mini mini-[type]"><div class="mini-label">LABEL</div><p>TEXT</p></div></td>
    <td width="50%" style="padding-left:5px;"><div class="mini mini-[type]"><div class="mini-label">LABEL</div><p>TEXT</p></div></td>
    </tr><tr valign="top">
    <td style="padding-right:5px;padding-top:10px;"><div class="mini mini-[type]"><div class="mini-label">LABEL</div><p>TEXT</p></div></td>
    <td style="padding-left:5px;padding-top:10px;"><div class="mini mini-[type]"><div class="mini-label">LABEL</div><p>TEXT</p></div></td>
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
                {"role": "system", "content": "You are an expert payments news editor producing HTML fragments for a fixed email template."},
                {"role": "user", "content": prompt + "\n\n---BEGIN DOCUMENT---\n" + document + "\n---END DOCUMENT---"}
            ],
            max_output_tokens=OPENAI_MAX_TOKENS,
        )
        ai_text       = resp.output_text
        usage         = getattr(resp, "usage", None) or {}
        input_tokens  = getattr(usage, "input_tokens",  None) or usage.get("input_tokens")
        output_tokens = getattr(usage, "output_tokens", None) or usage.get("output_tokens")
        model_used    = resp.model
        provider_label = f"OpenAI · {model_used}"

    elif LLM_PROVIDER == "anthropic":
        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=ANTHROPIC_MAX_TOKENS,
            system="You are an expert payments news editor producing HTML fragments for a fixed email template.",
            messages=[
                {"role": "user", "content": prompt + "\n\n---BEGIN DOCUMENT---\n" + document + "\n---END DOCUMENT---"}
            ],
        )
        ai_text        = resp.content[0].text
        input_tokens   = resp.usage.input_tokens
        output_tokens  = resp.usage.output_tokens
        model_used     = resp.model
        provider_label = f"Anthropic · {model_used}"

    # ── TOKEN USAGE + COST ───────────────────────────────────────────────────
    print({"model": model_used, "input_tokens": input_tokens, "output_tokens": output_tokens})

    PRICING = {
        "gpt-5.6-luna":              (0.20 / 1_000_000,  1.20 / 1_000_000),
        "gpt-5.6-terra":             (2.00 / 1_000_000, 12.00 / 1_000_000),
        "gpt-5.5":                   (5.00 / 1_000_000, 30.00 / 1_000_000),
        "gpt-4o-mini":               (0.15 / 1_000_000,  0.60 / 1_000_000),
        "gpt-4o":                    (2.50 / 1_000_000, 10.00 / 1_000_000),
        "claude-sonnet-4-6":         (3.00 / 1_000_000, 15.00 / 1_000_000),
        "claude-haiku-4-5-20251001": (0.80 / 1_000_000,  4.00 / 1_000_000),
        "claude-opus-4-6":           (15.0 / 1_000_000, 75.00 / 1_000_000)
    }
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
        "KEY_NUMBERS":  parse_key_numbers(blocks.get("KEY_NUMBERS", "")),
        "TOP_STORIES":  parse_stories(blocks.get("TOP_STORIES", "")),
        "RISK":         parse_stories(blocks.get("RISK", "")),
        "MACRO":        parse_stories(blocks.get("MACRO", "")),
        "EVENTS":       blocks.get("EVENTS", '<div class="muted">No upcoming events detected.</div>'),
        "TAKEAWAYS":    blocks.get("TAKEAWAYS", ""),
        "QUICK_LINKS":  blocks.get("QUICK_LINKS", ""),
        "FOOTER_NOTE": escape("Payments News • Auto-generated") + f' &nbsp;|&nbsp; <span style="font-style:italic;">Generated by {provider_label}</span>',
    }

    return fill_template(template, mapping)

def wrap_in_standard_template(inner_html: str, articles_count: int) -> str:
    now = datetime.now().strftime("%A, %d %B %Y • %H:%M")
    return f"""<!doctype html>
    <html>
    <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <style>
        body {{ margin:0; padding:0; background:#f5f7fb; font-family: Arial, sans-serif; color:#111827; }}
        .wrap {{ max-width: 980px; margin: 0 auto; padding: 24px; }}
        .card {{ background:#fff; border:1px solid #e5e7eb; border-radius:14px; box-shadow: 0 6px 20px rgba(17,24,39,.06); }}
        .pad {{ padding: 20px 22px; }}
        .hero {{ display:flex; align-items:center; justify-content:space-between; gap:16px; }}
        .title {{ font-size: 22px; margin:0; }}
        .sub {{ margin:6px 0 0; color:#6b7280; font-size: 13px; }}
        .pills {{ margin-top: 14px; display:flex; flex-wrap:wrap; gap:8px; }}
        .pill {{ display:inline-block; padding:6px 10px; border-radius:999px; background:#eef2ff; color:#3730a3; font-size:12px; border:1px solid #e0e7ff; }}
        h2 {{ margin: 18px 0 10px; font-size: 16px; }}
        h3 {{ margin: 10px 0 8px; font-size: 14px; }}
        .item {{ padding: 14px; border:1px solid #eef2f7; border-radius: 12px; background:#fbfdff; margin: 12px 0; }}
        .meta {{ display:flex; gap:8px; align-items:center; font-size: 12px; }}
        .src {{ font-weight:700; color:#2563eb; }}
        .tag {{ padding:3px 8px; border-radius:999px; background:#f3f4f6; border:1px solid #e5e7eb; color:#374151; }}
        ul {{ margin: 8px 0 0 18px; padding:0; }}
        li {{ margin: 6px 0; color:#374151; font-size: 13px; line-height: 1.45; }}
        .btn {{ display:inline-block; padding:8px 12px; border-radius: 10px; background:#2563eb; color:#fff; text-decoration:none; font-size: 12px; }}
        .muted {{ color:#6b7280; font-size: 13px; }}
        table {{ width:100%; border-collapse: collapse; margin-top: 8px; }}
        th, td {{ border-bottom: 1px solid #eef2f7; padding: 10px 8px; text-align:left; font-size: 13px; }}
        th {{ color:#6b7280; font-weight:600; }}
        .footer {{ margin-top:16px; color:#9ca3af; font-size: 12px; text-align:center; }}
    </style>
    </head>
    <body>
    <div class="wrap">
        <div class="card pad">
        <div class="hero">
            <div>
            <h1 class="title">Payments Industry Newsletter</h1>
            <p class="sub">{now} • {articles_count} items scanned</p>
            </div>
        </div>

        <!-- GPT content goes here -->
        {inner_html}

        <div class="footer">Payments News Bot • MVP</div>
        </div>
    </div>
    </body>
    </html>"""

# ========================================================================================

########## To-Do

def create_email_html(articles):
    """
    Create a formatted HTML email from articles
    """
    print("\n" + "="*70)
    print("STEP 2: CREATING EMAIL HTML")
    print("="*70)
    
    # Remove HTML tags from summaries
    def clean_html(text):
        return re.sub('<[^<]+?>', '', text)
    
    # Build the HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                background-color: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #1a1a1a;
                border-bottom: 3px solid #0066cc;
                padding-bottom: 10px;
                margin-top: 0;
            }}
            .date {{
                color: #666;
                font-size: 0.95em;
                margin-bottom: 30px;
            }}
            .stats {{
                background: #e8f4ff;
                padding: 15px;
                border-radius: 4px;
                margin-bottom: 20px;
                font-size: 0.9em;
                color: #555;
            }}
            .article {{
                margin-bottom: 25px;
                padding: 20px;
                background: #f9f9f9;
                border-left: 4px solid #0066cc;
                border-radius: 4px;
            }}
            .article-source {{
                color: #0066cc;
                font-size: 0.85em;
                font-weight: bold;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .article-title {{
                margin: 8px 0;
                color: #1a1a1a;
                font-size: 1.2em;
                font-weight: 600;
            }}
            .article-date {{
                color: #999;
                font-size: 0.85em;
                margin-bottom: 10px;
            }}
            .article-summary {{
                margin: 12px 0;
                color: #555;
                line-height: 1.6;
            }}
            .read-more {{
                display: inline-block;
                margin-top: 10px;
                padding: 8px 16px;
                background-color: #0066cc;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                font-size: 0.9em;
            }}
            .footer {{
                margin-top: 40px;
                padding-top: 20px;
                border-top: 2px solid #eee;
                text-align: center;
                color: #999;
                font-size: 0.85em;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📰 Payments Industry News Digest</h1>
            <div class="date">{datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")}</div>
            
            <div class="stats">
                📊 <strong>{len(articles)} articles</strong> from {len(RSS_FEEDS)} sources
            </div>
    """
    
    # Add each article
    for article in articles:
        summary = clean_html(article['summary'])
        
        # Truncate if too long
        if len(summary) > 400:
            summary = summary[:400] + "..."
        
        html += f"""
            <div class="article">
                <div class="article-source">{article['source']}</div>
                <div class="article-title">{article['title']}</div>
                <div class="article-date">📅 {article['published']}</div>
                <div class="article-summary">{summary}</div>
                <a href="{article['link']}" class="read-more">Read Full Article →</a>
            </div>
        """
    
    # Close HTML
    html += f"""
            <div class="footer">
                <p><strong>Payments News Bot</strong> - MVP Version</p>
                <p>Automatically generated at {datetime.now().strftime("%I:%M %p")}</p>
                <p style="margin-top: 15px; font-size: 0.8em;">
                    🤖 Next: Add AI summarization with Claude
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    print(f"✓ Email HTML created ({len(html)} characters)")
    
    return html

def print_email_preview(html_content, articles):
    """
    Print a text preview of the email to console
    """
    print("\n" + "="*70)
    print("STEP 3: EMAIL PREVIEW")
    print("="*70)
    
    print(f"\n📧 SUBJECT: Payments News Digest - {datetime.now().strftime('%b %d, %Y')}")
    print("\n" + "-"*70)
    print(f"PAYMENTS INDUSTRY NEWS DIGEST")
    print(f"{datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}")
    print(f"\n📊 {len(articles)} articles from {len(RSS_FEEDS)} sources")
    print("-"*70)
    
    for i, article in enumerate(articles, 1):
        print(f"\n[{i}] {article['source'].upper()}")
        print(f"Title: {article['title']}")
        print(f"Date: {article['published']}")
        print(f"Link: {article['link']}")
        
        # Clean and truncate summary
        summary = re.sub('<[^<]+?>', '', article['summary'])
        if len(summary) > 200:
            summary = summary[:200] + "..."
        print(f"Summary: {summary}")
        print("-"*70)
    
    print(f"\n✅ Full HTML email is ready ({len(html_content)} characters)")

# ========================================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("     PAYMENTS NEWS BOT")
    print("="*70)
    
    # Step 1: Fetch news
    articles = fetch_news()          # your RSS feeds
    scheme_articles = fetch_scheme_press()

    articles.extend(scheme_articles)

    
    if not articles:
        print("\n❌ No articles found!")
    else:
        # Step 2: Create email HTML
        email_html = generate_newsletter_html(client, articles, template_path="TEMPLATE.html")
        
        # Step 3: Print preview to console
        # print_email_preview(email_html, articles)
        
        # Optional: Save HTML file
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "GeneratedReports")
        os.makedirs(output_dir, exist_ok=True)
        filename = f"PaymentsNewsReport_{datetime.now().strftime('%d-%m-%y_%H-%M')}.html"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(email_html)

        print(f"\n💾 Full HTML saved to: GeneratedReports/{filename}")
        print(f"   Open this file in your browser to see the styled version!")

        print("\n✅ SUCCESS!")


# TO DO:
# Tailor the number of reports to pull from each place based on their priority and gain
# Attach as an email
# Lambda
# Store arrays on S3 buckets