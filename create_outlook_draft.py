"""
create_outlook_draft.py — open the latest generated newsletter as a draft in desktop Outlook.

Usage:
    python create_outlook_draft.py [path/to/PaymentsEmail_*.html]

Needs classic Outlook for Windows (not "new Outlook") and `pip install pywin32`.
Without an argument it picks the newest PaymentsEmail_*.html from GeneratedReports/ or
NewGitActionsGeneratedNewsletter/ (by the timestamp in the filename).
The draft is only displayed — nothing is sent. Add recipients and send it yourself.

The HTML goes in as the message body, so formatting is exactly what the template produced
(no browser copy/paste in between). Author photos are base64 in the file, which Outlook
blocks, so they are swapped for inline attachments referenced via cid:.
"""
import base64
import glob
import os
import re
import sys
import tempfile
from datetime import datetime

import win32com.client

HERE = os.path.dirname(os.path.abspath(__file__))
PR_ATTACH_CONTENT_ID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"
PR_ATTACHMENT_HIDDEN = "http://schemas.microsoft.com/mapi/proptag/0x7FFE000B"


# Local runs write to GeneratedReports/; files pulled from the GitHub Actions run land in
# NewGitActionsGeneratedNewsletter/. The newest email file across both is used.
SEARCH_DIRS = ["GeneratedReports", "NewGitActionsGeneratedNewsletter"]


def _generated_at(path: str) -> datetime:
    """Timestamp from PaymentsEmail_DD-MM-YY_HH-MM.html (file mtime is unreliable after git pull)."""
    m = re.search(r"_(\d{2}-\d{2}-\d{2}_\d{2}-\d{2})\.html$", path)
    if m:
        return datetime.strptime(m.group(1), "%d-%m-%y_%H-%M")
    return datetime.fromtimestamp(os.path.getmtime(path))


def latest_email_file() -> str:
    files = [
        f
        for d in SEARCH_DIRS
        for f in glob.glob(os.path.join(HERE, d, "PaymentsEmail_*.html"))
    ]
    if not files:
        sys.exit(f"No PaymentsEmail_*.html found in {' or '.join(SEARCH_DIRS)} — run NewsBot.py first.")
    return max(files, key=_generated_at)


def build_draft(path: str):
    """Create (and save) an Outlook draft from the HTML file; returns the MailItem."""
    with open(path, encoding="utf-8") as f:
        html = f.read()

    # Pull each base64 image out and point the <img> at a cid: instead.
    images = []  # (cid, bytes)

    def to_cid(m):
        cid = f"img{len(images)}@pymntnews"
        images.append((cid, base64.b64decode(m.group(2))))
        return f'src="cid:{cid}"'

    html = re.sub(r'src="data:image/(jpeg|png|gif);base64,([^"]+)"', to_cid, html)

    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)  # olMailItem
    mail.Subject = f"Payments Industry Newsletter — {datetime.now().strftime('%d %b %Y')}"

    with tempfile.TemporaryDirectory() as tmp:
        for i, (cid, data) in enumerate(images):
            img_path = os.path.join(tmp, f"photo{i}.jpg")
            with open(img_path, "wb") as f:
                f.write(data)
            att = mail.Attachments.Add(img_path)
            att.PropertyAccessor.SetProperty(PR_ATTACH_CONTENT_ID, cid)
            att.PropertyAccessor.SetProperty(PR_ATTACHMENT_HIDDEN, True)
        mail.HTMLBody = html
        mail.Save()  # copy attachments into the draft before the temp files vanish
    return mail, len(images)


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else latest_email_file()
    mail, n = build_draft(path)
    mail.Display()
    print(f"Draft opened from {os.path.basename(path)} with {n} inline image(s). Not sent.")


if __name__ == "__main__":
    main()
