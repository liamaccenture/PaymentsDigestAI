"""
preview.py — render the newsletter template with dummy data, no API call needed.
Run: python preview.py
Opens GeneratedReports/PREVIEW_browser.html and GeneratedReports/PREVIEW_email.html
"""
import os
import re
from datetime import datetime
from html import escape

# ── Copy rendering helpers from NewsBot so we don't trigger the LLM client init ──

FONT = "font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;"

TAG_INLINE = {
    "tag-risk":       "background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;",
    "tag-regulatory": "background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;",
    "tag-tech":       "background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0;",
    "tag-infra":      "background:#fff7ed;color:#c2410c;border:1px solid #fed7aa;",
    "tag-macro":      "background:#faf5ff;color:#7e22ce;border:1px solid #e9d5ff;",
    "tag-scheme":     "background:#ecfdf5;color:#065f46;border:1px solid #a7f3d0;",
}


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
            if "|" in line and ":" in line:
                for part in line.split("|"):
                    part = part.strip()
                    if ":" in part:
                        k, _, v = part.partition(":")
                        fields[k.strip()] = v.strip()
            elif ":" in line:
                key, _, val = line.partition(":")
                fields[key.strip()] = val.strip()

        src_tag  = fields.get("SRC", "")
        tag_raw  = fields.get("TAG", "")
        label    = fields.get("LABEL", "")
        head     = fields.get("HEAD", "")
        why      = fields.get("WHY", "")
        take     = fields.get("TAKE", "")
        consult  = fields.get("CONSULT", "")
        url      = fields.get("URL", "#")
        scheme   = fields.get("SCHEME", "")
        geo      = fields.get("GEO", "")

        tag_style = TAG_INLINE.get(tag_raw, "background:#f3f4f6;color:#374151;border:1px solid #e5e7eb;")

        extra_bullets = ""
        if scheme:
            extra_bullets += f'<li style="margin:4px 0;font-size:13px;line-height:1.45;{FONT}"><b>Scheme impact:</b> {escape(scheme)}</li>\n'
        if geo:
            extra_bullets += f'<li style="margin:4px 0;font-size:13px;line-height:1.45;{FONT}"><b>UK/EMEA relevance:</b> {escape(geo)}</li>\n'

        consult_li = (
            f'    <li style="margin:4px 0;font-size:13px;line-height:1.45;{FONT}"><b>Opportunity:</b> {escape(consult)}</li>\n'
            if consult else ""
        )

        html_parts.append(
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" class="story"'
            f' style="border:1px solid #d1d5db;border-radius:14px;margin-bottom:12px;background:#ffffff;">\n'
            f'<tr><td style="padding:14px;{FONT}">\n'
            f'  <table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation">\n'
            f'  <tr valign="middle">\n'
            f'    <td style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#4b5563;{FONT}">{escape(src_tag)}</td>\n'
            f'    <td align="right"><span class="tag {escape(tag_raw)}" style="font-size:11px;font-weight:600;border-radius:999px;padding:4px 9px;{tag_style}{FONT}">{escape(label)}</span></td>\n'
            f"  </tr>\n  </table>\n"
            f'  <h3 style="margin:8px 0 6px;font-size:14px;color:#111827;{FONT}">{escape(head)}</h3>\n'
            f'  <ul style="margin:10px 0 0;padding-left:18px;color:#374151;">\n'
            f'    <li style="margin:4px 0;font-size:13px;line-height:1.45;{FONT}"><b>Why it matters:</b> {escape(why)}</li>\n'
            f'    <li style="margin:4px 0;font-size:13px;line-height:1.45;{FONT}"><b>Key takeaway:</b> {escape(take)}</li>\n'
            f"{consult_li}{extra_bullets}"
            f"  </ul>\n"
            f'  <a href="{url}" class="btn" style="display:inline-block;margin-top:10px;padding:8px 14px;border-radius:10px;'
            f'background:#2563eb;font-size:12px;color:#ffffff;font-weight:600;text-decoration:none;{FONT}"'
            f' aria-label="Read more: {escape(head)}">Read &#8594;</a>\n'
            f"</td></tr>\n</table>"
        )
    return "\n".join(html_parts)


def parse_key_numbers(block_text: str) -> str:
    NUM_COLORS = {"kn-warn": "#c2410c", "kn-good": "#15803d", "kn-brand": "#2563eb"}
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
            f'<td width="25%" valign="top" height="1" style="{right_pad}">'
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" style="display:block;height:100%;background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;padding:14px 16px;text-decoration:none;color:inherit;box-sizing:border-box;">'
            f'<div style="font-size:24px;font-weight:800;color:{num_color};line-height:1;margin-bottom:3px;">{val}</div>'
            f'<div style="font-size:12px;color:#6b7280;line-height:1.3;">{label}</div>'
            f'<div style="font-size:10px;color:#6b7280;margin-top:5px;font-style:italic;">{src}</div>'
            f"</a></td>"
        )
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation"><tr>'
        + "".join(tds)
        + "</tr></table>"
    )


def parse_focus(block: str) -> tuple:
    title = subtitle = ""
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


# ── Author section (matches NewsBot.py) ──────────────────────────────────────
AUTHOR_SECTION_HTML = """
<table width="100%" cellpadding="22" cellspacing="0" border="0" bgcolor="#ffffff"
  style="background:#ffffff;border:1px solid #d1d5db;border-radius:16px;" role="presentation">
  <tr><td style="font-family:Arial,Helvetica,sans-serif;">
    <div style="font-size:16px;font-weight:700;padding-bottom:10px;border-bottom:1px solid #e5e7eb;color:#111827;margin-bottom:16px;">Your curators</div>
    <table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation">
      <tr valign="middle">
        <td width="50%" style="padding-right:16px;">
          <table cellpadding="0" cellspacing="0" border="0" role="presentation"><tr valign="middle">
            <td width="64" style="padding-right:12px;">
              <img src="data:image/jpeg;base64,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" width="52" height="52" alt="Liam Grimwood" style="border-radius:50%;display:block;">
            </td>
            <td>
              <div style="font-size:14px;font-weight:700;color:#111827;font-family:Arial,Helvetica,sans-serif;">Liam Grimwood</div>
            </td>
          </tr></table>
        </td>
        <td width="50%">
          <table cellpadding="0" cellspacing="0" border="0" role="presentation"><tr valign="middle">
            <td width="64" style="padding-right:12px;">
              <img src="data:image/jpeg;base64,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" width="52" height="52" alt="Morgan Moloney" style="border-radius:50%;display:block;">
            </td>
            <td>
              <div style="font-size:14px;font-weight:700;color:#111827;font-family:Arial,Helvetica,sans-serif;">Morgan Moloney</div>
            </td>
          </tr></table>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
"""

# ── Dummy AI blocks — edit these to test different content ────────────────────

DUMMY_BLOCKS = {
    "FOCUS": """
FOCUS_TITLE=FCA crypto gateway opens 30 September
FOCUS_SUBTITLE=UK firms must be authorised or exit market by deadline
""",

    "KEY_NUMBERS": """
VAL:£1.2bn|LABEL:FCA fines issued YTD|SRC:FCA|CLASS:kn-warn
URL:https://www.fca.org.uk/
---
VAL:30 Sep|LABEL:Crypto authorisation deadline|SRC:FCA|CLASS:kn-warn
URL:https://www.fca.org.uk/
---
VAL:+14%|LABEL:Faster Payments volume YoY|SRC:Pay.UK|CLASS:kn-good
URL:https://www.payuk.co.uk/
---
VAL:ISO 20022|LABEL:SWIFT migration phase 3|SRC:SWIFT|CLASS:kn-brand
URL:https://www.swift.com/
""",

    "TOP_STORIES": """
SRC:FCA|TAG:tag-regulatory|LABEL:Regulatory
HEAD:FCA crypto gateway opens — firms must apply or exit
WHY:Any UK crypto firm without authorisation cannot operate post-30 Sep.
TAKE:Compliance teams face urgent application deadline or wind-down planning.
CONSULT:Regulatory readiness assessment and authorisation support for crypto clients.
URL:https://www.fca.org.uk/
---
SRC:Pay.UK|TAG:tag-infra|LABEL:Infrastructure
HEAD:Faster Payments volume surges 14% in Q3 2026
WHY:Continued shift from cheque and card to instant credit push payments.
TAKE:Banks investing in FPS capacity to meet demand; fraud controls under pressure.
URL:https://www.payuk.co.uk/
---
SRC:Visa|TAG:tag-scheme|LABEL:Scheme
HEAD:Visa updates interchange for contactless transactions in EMEA
WHY:Fee changes affect acquirer economics across UK/EU merchant portfolios.
TAKE:Acquirers and PSPs need to reprice merchant agreements before Jan 2027.
CONSULT:Interchange impact modelling and repricing strategy for acquiring clients.
URL:https://usa.visa.com/about-visa/newsroom/press-releases.html
SCHEME:Visa EMEA interchange restructure affects contactless card-present rates.
""",

    "RISK": """
SRC:FCA|TAG:tag-risk|LABEL:Risk
HEAD:FCA warns on APP fraud reimbursement gaps at smaller PSPs
WHY:Smaller PSPs may not have systems to meet mandatory reimbursement obligations.
TAKE:PSPs below threshold need to audit fraud controls and reimbursement workflows.
CONSULT:APP fraud control gap analysis and remediation for mid-tier PSP clients.
URL:https://www.fca.org.uk/
---
SRC:ECB|TAG:tag-regulatory|LABEL:Regulatory
HEAD:ECB publishes revised DORA supervisory expectations for payment firms
WHY:Stricter ICT risk management expectations apply from Q1 2027.
TAKE:Payment institutions must update resilience frameworks and third-party registers.
URL:https://www.ecb.europa.eu/
""",

    "MACRO": """
SRC:Bank of England|TAG:tag-macro|LABEL:Macro
HEAD:BoE holds base rate at 4.5% amid persistent services inflation
WHY:Elevated rates sustain pressure on consumer credit and BNPL default rates.
TAKE:Payments firms with credit exposure should stress-test for prolonged high-rate environment.
URL:https://www.bankofengland.co.uk/
""",

    "EVENTS": """
<table class="events" width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation">
  <thead>
    <tr>
      <th scope="col" style="color:#4b5563;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.06em;padding:8px 10px;border-bottom:2px solid #e5e7eb;text-align:left;">Date</th>
      <th scope="col" style="color:#4b5563;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.06em;padding:8px 10px;border-bottom:2px solid #e5e7eb;text-align:left;">Event</th>
      <th scope="col" style="color:#4b5563;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.06em;padding:8px 10px;border-bottom:2px solid #e5e7eb;text-align:left;">Type</th>
      <th scope="col" style="color:#4b5563;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.06em;padding:8px 10px;border-bottom:2px solid #e5e7eb;text-align:left;">Relevance</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="padding:9px 10px;border-bottom:1px solid #e5e7eb;font-weight:600;white-space:nowrap;font-size:13px;">30 Sep 2026</td>
      <td style="padding:9px 10px;border-bottom:1px solid #e5e7eb;font-size:13px;"><a href="https://www.fca.org.uk/">UK cryptoasset authorisation gateway opens</a></td>
      <td style="padding:9px 10px;border-bottom:1px solid #e5e7eb;"><span class="ev-badge ev-reg" style="background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;font-size:12px;font-weight:600;border-radius:999px;padding:2px 7px;">Reg</span></td>
      <td style="padding:9px 10px;border-bottom:1px solid #e5e7eb;font-size:13px;">High</td>
    </tr>
    <tr style="background:#f8faff;">
      <td style="padding:9px 10px;border-bottom:1px solid #e5e7eb;font-weight:600;white-space:nowrap;font-size:13px;">Nov 2026</td>
      <td style="padding:9px 10px;border-bottom:1px solid #e5e7eb;font-size:13px;"><a href="https://www.ebaclearing.eu/">STEP2 DKK go-live (EBA Clearing)</a></td>
      <td style="padding:9px 10px;border-bottom:1px solid #e5e7eb;"><span class="ev-badge ev-infra" style="background:#fff7ed;color:#c2410c;border:1px solid #fed7aa;font-size:12px;font-weight:600;border-radius:999px;padding:2px 7px;">Infra</span></td>
      <td style="padding:9px 10px;border-bottom:1px solid #e5e7eb;font-size:13px;">High</td>
    </tr>
    <tr>
      <td style="padding:9px 10px;border-bottom:1px solid #e5e7eb;font-weight:600;white-space:nowrap;font-size:13px;">1 Jan 2027</td>
      <td style="padding:9px 10px;border-bottom:1px solid #e5e7eb;font-size:13px;"><a href="https://www.bankofengland.co.uk/">Basel 3.1 UK go-live</a></td>
      <td style="padding:9px 10px;border-bottom:1px solid #e5e7eb;"><span class="ev-badge ev-reg" style="background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;font-size:12px;font-weight:600;border-radius:999px;padding:2px 7px;">Reg</span></td>
      <td style="padding:9px 10px;border-bottom:1px solid #e5e7eb;font-size:13px;">High</td>
    </tr>
  </tbody>
</table>
""",

    "TAKEAWAYS": """
<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation"><tr valign="top">
<td width="50%" style="padding-right:5px;"><div class="mini mini-risk" style="border-left:4px solid #b91c1c;border-radius:0 12px 12px 0;padding:10px 12px;background:#fef9f9;"><div class="mini-label" style="font-size:12px;font-weight:700;color:#b91c1c;text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px;font-family:Arial,sans-serif;">Risk signal</div><p style="margin:0;font-size:12px;color:#111827;line-height:1.4;font-family:Arial,sans-serif;">APP fraud reimbursement gaps at smaller PSPs may trigger FCA enforcement action.</p></div></td>
<td width="50%" style="padding-left:5px;"><div class="mini mini-scheme" style="border-left:4px solid #065f46;border-radius:0 12px 12px 0;padding:10px 12px;background:#f0fdfb;"><div class="mini-label" style="font-size:12px;font-weight:700;color:#065f46;text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px;font-family:Arial,sans-serif;">Scheme change</div><p style="margin:0;font-size:12px;color:#111827;line-height:1.4;font-family:Arial,sans-serif;">Visa EMEA interchange update requires acquirers to reprice merchant agreements by Jan 2027.</p></div></td>
</tr><tr valign="top">
<td style="padding-right:5px;padding-top:10px;"><div class="mini" style="border-left:4px solid #2563eb;border-radius:0 12px 12px 0;padding:10px 12px;background:#f8faff;"><div class="mini-label" style="font-size:12px;font-weight:700;color:#2563eb;text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px;font-family:Arial,sans-serif;">Regulatory deadline</div><p style="margin:0;font-size:12px;color:#111827;line-height:1.4;font-family:Arial,sans-serif;">UK crypto authorisation gateway opens 30 Sep — unlicensed firms must exit or apply immediately.</p></div></td>
<td style="padding-left:5px;padding-top:10px;"><div class="mini mini-macro" style="border-left:4px solid #7e22ce;border-radius:0 12px 12px 0;padding:10px 12px;background:#fdf8ff;"><div class="mini-label" style="font-size:12px;font-weight:700;color:#7e22ce;text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px;font-family:Arial,sans-serif;">Macro watch</div><p style="margin:0;font-size:12px;color:#111827;line-height:1.4;font-family:Arial,sans-serif;">BoE holds at 4.5%; payment firms with credit exposure should stress-test for prolonged high rates.</p></div></td>
</tr></table>
""",

    "QUICK_LINKS": """
<a href="https://www.fca.org.uk/">FCA sets out final cryptoasset authorisation rules</a>
<a href="https://www.bankofengland.co.uk/">BoE holds base rate at 4.5% — MPC minutes</a>
<a href="https://www.swift.com/">SWIFT ISO 20022 migration: phase 3 timeline confirmed</a>
<a href="https://www.ebaclearing.eu/">EBA Clearing STEP2 DKK go-live announcement</a>
<a href="https://www.finextra.com/">Finextra: Open banking API calls hit 1bn/month in UK</a>
<a href="https://www.pymnts.com/">PYMNTS: BNPL defaults rise as consumer credit tightens</a>
""",
}

# ── Render ────────────────────────────────────────────────────────────────────

def render(template_path: str, max_width: str, article_count: int = 87) -> str:
    focus_title, focus_subtitle = parse_focus(DUMMY_BLOCKS["FOCUS"])
    today = datetime.now().strftime("%d %b %Y")
    date_line = f"{today} • {article_count} items scanned"

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    mapping = {
        "TITLE":          "Payments Industry Newsletter",
        "DATE_LINE":      escape(date_line),
        "FOCUS_TITLE":    escape(focus_title),
        "FOCUS_SUBTITLE": escape(focus_subtitle),
        "KEY_NUMBERS":    parse_key_numbers(DUMMY_BLOCKS["KEY_NUMBERS"]),
        "TOP_STORIES":    parse_stories(DUMMY_BLOCKS["TOP_STORIES"]),
        "RISK":           parse_stories(DUMMY_BLOCKS["RISK"]),
        "MACRO":          parse_stories(DUMMY_BLOCKS["MACRO"]),
        "EVENTS":         DUMMY_BLOCKS["EVENTS"],
        "TAKEAWAYS":      DUMMY_BLOCKS["TAKEAWAYS"],
        "QUICK_LINKS":    DUMMY_BLOCKS["QUICK_LINKS"],
        "AI_PROVIDER":    "Preview mode (no API call)",
        "AUTHORS":        AUTHOR_SECTION_HTML,
        "MAX_WIDTH":      max_width,
        "FOOTER_NOTE":    "Payments News &bull; Preview mode",
    }

    return fill_template(template, mapping)


if __name__ == "__main__":
    import sys
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "browser"

    base = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(base, "GeneratedReports")
    os.makedirs(out_dir, exist_ok=True)

    if mode == "email":
        html = render(os.path.join(base, "TEMPLATE_EMAIL.html"), max_width="680")
        out_path = os.path.join(out_dir, "PREVIEW_email.html")
        print(f"Email preview   : GeneratedReports/PREVIEW_email.html")
    else:
        html = render(os.path.join(base, "TEMPLATE.html"), max_width="1080")
        out_path = os.path.join(out_dir, "PREVIEW_browser.html")
        print(f"Browser preview : GeneratedReports/PREVIEW_browser.html")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    os.startfile(out_path)
