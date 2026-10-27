"""
make_msg.py — build an unsent Outlook draft (.msg) from a generated PaymentsEmail_*.html, with no
Outlook or Windows needed, so it can run in GitHub Actions on Linux.

Usage:
    python make_msg.py [path/to/PaymentsEmail_*.html]

The layout mirrors what classic Outlook itself writes for a saved draft: MSGFLAG_UNSENT is set so it
opens as an editable draft, the HTML is stored as-is (PR_HTML, UTF-8) and the author photos are
inline attachments referenced by cid: (ATT_MHTML_REF), so they are embedded rather than attached.
Written with extract_msg's OleWriter (pip install extract-msg).
"""
import base64
import glob
import os
import re
import struct
import sys
from datetime import datetime

from extract_msg.ole_writer import OleWriter

HERE = os.path.dirname(os.path.abspath(__file__))
SEARCH_DIRS = ["GeneratedReports", "NewGitActionsGeneratedNewsletter"]

PT_LONG, PT_BOOLEAN, PT_UNICODE, PT_BINARY = 0x0003, 0x000B, 0x001F, 0x0102
MSGFLAG_UNSENT, MSGFLAG_HASATTACH = 0x08, 0x10
ATT_MHTML_REF = 0x04
STORE_UNICODE_OK = 0x00040000
PROP_READABLE_WRITABLE = 0x06  # PROPATTR_READABLE | PROPATTR_WRITABLE


def _generated_at(path: str) -> datetime:
    m = re.search(r"_(\d{2}-\d{2}-\d{2}_\d{2}-\d{2})\.html$", path)
    if m:
        return datetime.strptime(m.group(1), "%d-%m-%y_%H-%M")
    return datetime.fromtimestamp(os.path.getmtime(path))


def latest_email_file() -> str:
    files = [
        f for d in SEARCH_DIRS for f in glob.glob(os.path.join(HERE, d, "PaymentsEmail_*.html"))
    ]
    if not files:
        sys.exit(f"No PaymentsEmail_*.html found in {' or '.join(SEARCH_DIRS)} — run NewsBot.py first.")
    return max(files, key=_generated_at)


def html_to_rtf_stream(html: str) -> bytes:
    r"""HTML wrapped as RTF-encapsulated HTML (\fromhtml1) in the *uncompressed* compressed-RTF container.

    Outlook ignores PR_HTML on an unsent draft and builds the body from this RTF copy instead.
    Non-ASCII becomes numeric entities first so the RTF is pure ASCII; the HTML sits in one
    \htmltag group, which Outlook de-encapsulates verbatim.
    """
    ascii_html = html.encode("ascii", "xmlcharrefreplace").decode("ascii")
    ascii_html = ascii_html.replace("\r", "").replace("\n", " ")
    esc = ascii_html.replace("\\", "\\\\").replace("{", r"\{").replace("}", r"\}")
    rtf = (
        r"{\rtf1\ansi\ansicpg1252\fromhtml1 \deff0{\fonttbl{\f0\fswiss Arial;}}"
        r"{\*\htmltag64 " + esc + "}}"
    ).encode("ascii")
    # Header: COMPSIZE (data + 12), RAWSIZE, COMPTYPE 'MELA' (uncompressed), CRC (unused for MELA).
    return struct.pack("<II", len(rtf) + 12, len(rtf)) + b"MELA" + struct.pack("<I", 0) + rtf



class _Props:
    """Collects MAPI properties for one storage and writes the stream + __properties_version1.0."""

    def __init__(self, writer: OleWriter, base: str, header: bytes):
        self.w, self.base, self.header, self.entries = writer, base, header, []

    def _add(self, tag: int, ptype: int, value8: bytes):
        self.entries.append(struct.pack("<IIQ", (tag << 16) | ptype, PROP_READABLE_WRITABLE, int.from_bytes(value8, "little")))

    def long(self, tag: int, v: int):
        self._add(tag, PT_LONG, struct.pack("<i", v) + b"\0" * 4)

    def boolean(self, tag: int, v: bool):
        self._add(tag, PT_BOOLEAN, struct.pack("<H", int(v)) + b"\0" * 6)

    def _stream(self, tag: int, ptype: int, data: bytes, size_field: int):
        self.w.addEntry(f"{self.base}__substg1.0_{tag:04X}{ptype:04X}", data)
        self._add(tag, ptype, struct.pack("<I", size_field) + b"\0" * 4)

    def string(self, tag: int, v: str):
        data = v.encode("utf-16-le")
        self._stream(tag, PT_UNICODE, data, len(data) + 2)

    def binary(self, tag: int, data: bytes):
        self._stream(tag, PT_BINARY, data, len(data))

    def finish(self):
        self.w.addEntry(f"{self.base}__properties_version1.0", self.header + b"".join(self.entries))


def build_msg(html_path: str, msg_path: str | None = None, subject: str | None = None) -> tuple[str, int]:
    """Write an unsent .msg next to the HTML (or at msg_path); returns (path, n_inline_images)."""
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    images = []  # (cid, subtype, bytes)

    def to_cid(m):
        cid = f"img{len(images)}@pymntnews"
        images.append((cid, m.group(1), base64.b64decode(m.group(2))))
        return f'src="cid:{cid}"'

    html = re.sub(r'src="data:image/(jpeg|png|gif);base64,([^"]+)"', to_cid, html)
    subject = subject or f"Payments Tech Industry Digest — {datetime.now().strftime('%d %b %Y')}"

    w = OleWriter()
    # Required (empty) named-property mapping storage.
    for name in ("00020102", "00030102", "00040102"):
        w.addEntry(f"__nameid_version1.0/__substg1.0_{name}", b"")

    n = len(images)
    # 32-byte top-level header: 8 reserved, next recipient id, next attachment id, recipient count,
    # attachment count, 8 reserved.
    top = _Props(w, "", b"\0" * 8 + struct.pack("<IIII", 0, n, 0, n) + b"\0" * 8)
    top.string(0x001A, "IPM.Note")
    top.string(0x0037, subject)
    top.string(0x0070, subject)
    top.string(0x1000, "This newsletter is best viewed in an HTML-capable email client.")
    top.binary(0x1013, html.encode("utf-8"))
    top.binary(0x1009, html_to_rtf_stream(html))  # PR_RTF_COMPRESSED
    top.boolean(0x0E1F, True)  # PR_RTF_IN_SYNC
    top.long(0x1016, 3)  # PR_NATIVE_BODY_INFO: HTML is the real body (else Outlook shows the text one)
    top.long(0x3FDE, 65001)  # PR_INTERNET_CPID = UTF-8
    top.long(0x3FF1, 0x809)  # locale: English (UK)
    top.long(0x0017, 1)  # importance: normal
    top.long(0x0036, 0)  # sensitivity: none
    top.long(0x0E07, MSGFLAG_UNSENT | (MSGFLAG_HASATTACH if n else 0))
    top.boolean(0x0E1B, bool(n))
    # Without this, Outlook rejects the file ("Cannot read the item") because the strings are Unicode.
    top.long(0x340D, STORE_UNICODE_OK)  # PR_STORE_SUPPORT_MASK
    top.finish()

    for i, (cid, subtype, data) in enumerate(images):
        ext = "jpg" if subtype == "jpeg" else subtype
        a = _Props(w, f"__attach_version1.0_#{i:08X}/", b"\0" * 8)
        a.long(0x0E21, i)  # PR_ATTACH_NUM
        a.long(0x0FFE, 7)  # PR_OBJECT_TYPE: MAPI_ATTACH
        a.long(0x3705, 1)  # ATTACH_BY_VALUE
        a.long(0x370B, -1)  # PR_RENDERING_POSITION: not positioned (inline)
        a.string(0x3001, f"photo{i}.{ext}")  # display name
        a.binary(0x3701, data)
        a.string(0x3703, f".{ext}")
        a.string(0x3704, f"photo{i}.{ext}")
        a.string(0x3707, f"photo{i}.{ext}")
        a.string(0x370E, f"image/{subtype}")
        a.string(0x3712, cid)
        a.long(0x3714, ATT_MHTML_REF)  # inline: shown in the body, not in the attachment well
        a.boolean(0x7FFE, True)  # hidden
        a.finish()

    msg_path = msg_path or os.path.splitext(html_path)[0] + ".msg"
    w.write(msg_path)
    return msg_path, n


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else latest_email_file()
    out, n = build_msg(src)
    print(f"Message saved: {out} ({n} inline image(s)). Double-click it to open the draft.")
