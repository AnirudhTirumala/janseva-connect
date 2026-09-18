import math
import os
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
from app.core.config import settings
from app.core.timeutils import utcnow

# Old records retain their existing paths for read-only compatibility; newly
# generated files always use the deployer's durable STORAGE_PATH.
LEGACY_CERT_DIR = (Path(__file__).resolve().parents[1] / "generated_certificates").resolve()

FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts")

# JanSeva Connect brand palette (matches the web app's Tailwind theme) so the
# certificate feels like part of the same product, not a generic template.
PANCHAYAT_900 = HexColor("#0D2019")
PANCHAYAT_700 = HexColor("#153328")
PANCHAYAT_600 = HexColor("#1E4638")
PANCHAYAT_500 = HexColor("#2E5C4A")
PANCHAYAT_100 = HexColor("#CFE0D6")
PANCHAYAT_50 = HexColor("#EAF0EC")
MARIGOLD_600 = HexColor("#B87220")
MARIGOLD_500 = HexColor("#DC8F2A")
MARIGOLD_300 = HexColor("#F0B860")
MARIGOLD_100 = HexColor("#FBE8C8")
INK = HexColor("#1C1C1A")
PAPER = HexColor("#FDFCF7")

_FONTS_REGISTERED = False


def certificate_dir() -> Path:
    directory = (settings.storage_path / "certificates").resolve()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def safe_certificate_path(file_path: str | None) -> Path | None:
    if not file_path:
        return None
    candidate = Path(file_path).resolve()
    roots = (certificate_dir(), LEGACY_CERT_DIR)
    if not any(candidate.is_relative_to(root) for root in roots):
        return None
    return candidate if candidate.is_file() else None


def delete_certificate_file(file_path: str | None) -> None:
    candidate = safe_certificate_path(file_path)
    if candidate:
        candidate.unlink(missing_ok=True)


def _register_fonts():
    """Registers the bundled Liberation Serif family (SIL OFL licensed, see
    assets/fonts/LICENSE.txt) once per process. A proper serif reads far more
    like an official document than the base-14 Helvetica used before, and
    the italic cut doubles as a tasteful stand-in for a signature."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    pdfmetrics.registerFont(TTFont("CertSerif", os.path.join(FONT_DIR, "LiberationSerif-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("CertSerif-Bold", os.path.join(FONT_DIR, "LiberationSerif-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("CertSerif-Italic", os.path.join(FONT_DIR, "LiberationSerif-Italic.ttf")))
    pdfmetrics.registerFont(TTFont("CertSerif-BoldItalic", os.path.join(FONT_DIR, "LiberationSerif-BoldItalic.ttf")))
    _FONTS_REGISTERED = True


def _wrap(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines, line = [], ""
    for word in words:
        if len(line) + len(word) + 1 <= max_chars:
            line = f"{line} {word}".strip()
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _draw_circular_text(c, cx, cy, radius, text, font, size, start_deg=90, clockwise=True, color=PANCHAYAT_700):
    """Places `text` letter-by-letter around a circle of the given radius,
    used for the ring of text around the official seal - the one thing a
    flat drawImage can't fake, since every letter needs its own rotation."""
    c.setFillColor(color)
    c.setFont(font, size)
    direction = -1 if clockwise else 1
    widths = [pdfmetrics.stringWidth(ch, font, size) for ch in text]
    total_width = sum(widths) or 1
    total_deg = (total_width / (2 * math.pi * radius)) * 360
    angle = start_deg + (total_deg / 2) * direction
    for ch, w in zip(text, widths):
        char_deg = (w / total_width) * total_deg
        angle -= (char_deg / 2) * direction
        rad = math.radians(angle)
        x = cx + radius * math.cos(rad)
        y = cy + radius * math.sin(rad)
        c.saveState()
        c.translate(x, y)
        c.rotate(angle - 90 if clockwise else angle + 90)
        c.drawCentredString(0, 0, ch)
        c.restoreState()
        angle -= (char_deg / 2) * direction


def _draw_seal(c, cx, cy, small_label="JANSEVA CONNECT", big_label="OFFICIAL SEAL", rotation=-11):
    """An original decorative seal (not a reproduction of any government
    emblem) - concentric rings, a ring of circular text, and a central
    star-in-sunburst motif, tinted and rotated like a real ink stamp."""
    c.saveState()
    c.translate(cx, cy)
    c.rotate(rotation)
    c.setFillAlpha(0.82)
    c.setStrokeAlpha(0.82)

    outer_r = 19 * mm
    c.setStrokeColor(PANCHAYAT_700)
    c.setLineWidth(1.3)
    c.circle(0, 0, outer_r, stroke=1, fill=0)
    c.setLineWidth(0.6)
    c.circle(0, 0, outer_r - 2.2 * mm, stroke=1, fill=0)
    c.circle(0, 0, outer_r - 12.5 * mm, stroke=1, fill=0)

    for i in range(40):
        deg = i * 9
        rad = math.radians(deg)
        r = outer_r - 1.1 * mm
        c.setFillColor(MARIGOLD_500)
        c.circle(r * math.cos(rad), r * math.sin(rad), 0.35 * mm, stroke=0, fill=1)

    _draw_circular_text(c, 0, 0, outer_r - 5.4 * mm, f"\u2022 {small_label} ", "CertSerif-Bold", 6.6, start_deg=90, clockwise=True, color=PANCHAYAT_700)
    _draw_circular_text(c, 0, 0, outer_r - 5.4 * mm, f"\u2022 {big_label} ", "CertSerif-Bold", 6.6, start_deg=270, clockwise=True, color=PANCHAYAT_700)

    inner_r = outer_r - 12.5 * mm
    c.setStrokeColor(MARIGOLD_500)
    c.setLineWidth(0.5)
    for i in range(16):
        deg = i * 22.5
        rad = math.radians(deg)
        x1, y1 = (inner_r - 3 * mm) * math.cos(rad), (inner_r - 3 * mm) * math.sin(rad)
        x2, y2 = (inner_r - 0.8 * mm) * math.cos(rad), (inner_r - 0.8 * mm) * math.sin(rad)
        c.line(x1, y1, x2, y2)

    star_r_outer, star_r_inner = 6.8 * mm, 2.8 * mm
    path = c.beginPath()
    for i in range(10):
        deg = -90 + i * 36
        r = star_r_outer if i % 2 == 0 else star_r_inner
        x, y = r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg))
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.close()
    c.setFillColor(PANCHAYAT_700)
    c.setStrokeColor(PANCHAYAT_700)
    c.setLineWidth(0.4)
    c.drawPath(path, stroke=1, fill=1)

    c.restoreState()


def _draw_frame_and_background(c, width, height):
    """Parchment-toned page with a double-rule border and small corner
    flourishes - the base every certificate is built on."""
    c.setFillColor(PAPER)
    c.rect(0, 0, width, height, stroke=0, fill=1)

    margin = 10 * mm
    outer = margin
    inner = margin + 2.6 * mm

    c.setStrokeColor(PANCHAYAT_700)
    c.setLineWidth(1.6)
    c.rect(outer, outer, width - 2 * outer, height - 2 * outer, stroke=1, fill=0)
    c.setStrokeColor(MARIGOLD_500)
    c.setLineWidth(0.7)
    c.rect(inner, inner, width - 2 * inner, height - 2 * inner, stroke=1, fill=0)

    for cx, cy in [(outer, outer), (width - outer, outer), (outer, height - outer), (width - outer, height - outer)]:
        c.setFillColor(MARIGOLD_500)
        d = 2.6 * mm
        path = c.beginPath()
        path.moveTo(cx, cy + d)
        path.lineTo(cx + d, cy)
        path.lineTo(cx, cy - d)
        path.lineTo(cx - d, cy)
        path.close()
        c.drawPath(path, stroke=0, fill=1)
        c.setFillColor(PANCHAYAT_700)
        c.circle(cx, cy, 0.9 * mm, stroke=0, fill=1)

    c.saveState()
    c.setFillColor(PANCHAYAT_500)
    c.setFillAlpha(0.05)
    c.setFont("CertSerif-Bold", 60)
    c.translate(width / 2, height / 2)
    c.rotate(38)
    c.drawCentredString(0, 0, "JANSEVA CONNECT")
    c.restoreState()


def _draw_letterhead(c, width, top_y, address_line):
    """Emblem + JANSEVA CONNECT wordmark + office address, centred, used
    identically at the top of every certificate/approval so the office
    identity is always the first thing the eye lands on."""
    emblem_cy = top_y
    c.setFillColor(PANCHAYAT_50)
    c.setStrokeColor(PANCHAYAT_700)
    c.setLineWidth(1)
    c.circle(width / 2, emblem_cy, 9 * mm, stroke=1, fill=1)
    c.setStrokeColor(MARIGOLD_500)
    c.setLineWidth(0.5)
    c.circle(width / 2, emblem_cy, 7.3 * mm, stroke=1, fill=0)
    star_r_outer, star_r_inner = 4.6 * mm, 1.9 * mm
    path = c.beginPath()
    for i in range(10):
        deg = -90 + i * 36
        r = star_r_outer if i % 2 == 0 else star_r_inner
        x = width / 2 + r * math.cos(math.radians(deg))
        y = emblem_cy + r * math.sin(math.radians(deg))
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.close()
    c.setFillColor(MARIGOLD_500)
    c.drawPath(path, stroke=0, fill=1)

    c.setFillColor(PANCHAYAT_700)
    c.setFont("CertSerif-Bold", 22)
    c.drawCentredString(width / 2, top_y - 15 * mm, "JANSEVA CONNECT")
    c.setFillColor(MARIGOLD_600)
    c.setFont("CertSerif-Bold", 8.5)
    c.drawCentredString(width / 2, top_y - 20.5 * mm, "A N D H R A   P R A D E S H   P A N C H A Y A T   S E R V I C E S")
    c.setFillColor(INK)
    c.setFont("CertSerif", 9.5)
    c.drawCentredString(width / 2, top_y - 26 * mm, address_line)

    rule_y = top_y - 30 * mm
    c.setStrokeColor(MARIGOLD_500)
    c.setLineWidth(0.8)
    c.line(width / 2 - 45 * mm, rule_y, width / 2 - 4 * mm, rule_y)
    c.line(width / 2 + 4 * mm, rule_y, width / 2 + 45 * mm, rule_y)
    c.setFillColor(MARIGOLD_500)
    diamond = c.beginPath()
    diamond.moveTo(width / 2, rule_y + 1.6 * mm)
    diamond.lineTo(width / 2 + 1.6 * mm, rule_y)
    diamond.lineTo(width / 2, rule_y - 1.6 * mm)
    diamond.lineTo(width / 2 - 1.6 * mm, rule_y)
    diamond.close()
    c.drawPath(diamond, stroke=0, fill=1)
    return rule_y


def _draw_qr(c, x, y, size, data, caption):
    widget = QrCodeWidget(data)
    b = widget.getBounds()
    w, h = b[2] - b[0], b[3] - b[1]
    drawing = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
    drawing.add(widget)
    renderPDF.draw(drawing, c, x, y)
    c.setFont("CertSerif", 6)
    c.setFillColor(INK)
    c.drawCentredString(x + size / 2, y - 3.2 * mm, caption)


def _draw_signature_block(c, width, sign_y, issuer_label, issuer_name):
    c.setFont("CertSerif-Italic", 17)
    c.setFillColor(PANCHAYAT_900)
    c.drawString(25 * mm, sign_y + 5.5 * mm, issuer_name)
    c.setStrokeColor(INK)
    c.setLineWidth(0.6)
    c.line(25 * mm, sign_y + 2 * mm, 85 * mm, sign_y + 2 * mm)
    c.setFont("CertSerif", 9)
    c.setFillColor(INK)
    c.drawString(25 * mm, sign_y - 3.5 * mm, issuer_name)
    c.setFont("CertSerif", 7.5)
    c.setFillColor(PANCHAYAT_600)
    c.drawString(25 * mm, sign_y - 8 * mm, issuer_label)
    _draw_seal(c, width - 45 * mm, sign_y + 6 * mm)


def _draw_footer(c, width, cert_number, issued_date, verify_payload):
    footer_y = 20 * mm
    c.setStrokeColor(MARIGOLD_300)
    c.setLineWidth(0.5)
    c.line(16 * mm, footer_y + 9 * mm, width - 40 * mm, footer_y + 9 * mm)
    c.setFont("CertSerif", 7)
    c.setFillColor(PANCHAYAT_600)
    c.drawString(16 * mm, footer_y + 3 * mm, "This is a digitally generated document issued through the JanSeva Connect platform.")
    c.drawString(16 * mm, footer_y - 2 * mm, f"Reference: {cert_number}  \u00b7  Generated: {issued_date}")
    _draw_qr(c, width - 34 * mm, footer_y - 4 * mm, 18 * mm, verify_payload, "Scan for details")


CERT_TITLES = {
    "income": "INCOME CERTIFICATE",
    "residence": "RESIDENCE CERTIFICATE",
    "birth": "BIRTH CERTIFICATE",
}


def generate_approval_pdf(application, member, scheme, reviewed_by_name: str) -> str:
    """Renders a formal, certificate-styled approval letter for a citizen
    whose scheme application was approved, matching generate_certificate_pdf's
    look so every JanSeva Connect document feels like part of one family."""
    _register_fonts()
    filename = f"approval_{application.id}.pdf"
    filepath = certificate_dir() / filename

    c = canvas.Canvas(str(filepath), pagesize=A4)
    width, height = A4

    _draw_frame_and_background(c, width, height)
    address_line = f"{member.village}, {member.district or ''}, {member.state}".replace(" ,", ",")
    rule_y = _draw_letterhead(c, width, height - 20 * mm, address_line)

    approved_date = application.reviewed_at.strftime('%d %B %Y') if application.reviewed_at else utcnow().strftime('%d %B %Y')
    app_no = f"APP-{application.id:06d}"

    c.setFont("CertSerif-Bold", 17)
    c.setFillColor(PANCHAYAT_700)
    c.drawCentredString(width / 2, rule_y - 12 * mm, "SCHEME APPROVAL CERTIFICATE")

    c.setFont("CertSerif", 9.5)
    c.setFillColor(INK)
    c.drawString(25 * mm, rule_y - 22 * mm, f"Application No: {app_no}")
    c.drawRightString(width - 25 * mm, rule_y - 22 * mm, f"Date: {approved_date}")

    body_y = rule_y - 36 * mm
    c.setFont("CertSerif", 11.5)
    c.setFillColor(INK)
    text = (
        f"This is to certify that the application submitted by Mr./Ms. {member.full_name}, "
        f"resident of {member.address}, {member.village}, for the scheme \u201c{scheme.name}\u201d "
        f"has been reviewed and APPROVED by the JanSeva Connect office."
    )
    lines = _wrap(text, 78)
    for i, ln in enumerate(lines):
        c.drawString(28 * mm, body_y - (i * 7 * mm), ln)

    sign_y = body_y - (len(lines) * 7 * mm) - 32 * mm
    _draw_signature_block(c, width, sign_y, "Approving Officer, JanSeva Connect", reviewed_by_name)
    _draw_footer(c, width, app_no, approved_date, f"JanSeva Connect | Scheme approval | {app_no} | {member.full_name} | {scheme.name} | Approved {approved_date} | By {reviewed_by_name}")

    c.showPage()
    c.save()
    return str(filepath)


def generate_certificate_pdf(certificate_number: str, certificate_type: str, member, issued_by_name: str, certificate_title: str | None = None) -> str:
    """Renders an official-styled certificate PDF (bordered, sealed, signed)
    and saves it to disk. Returns the file path stored on the Certificate record.
    """
    _register_fonts()
    filename = f"{certificate_number}.pdf"
    filepath = certificate_dir() / filename

    c = canvas.Canvas(str(filepath), pagesize=A4)
    width, height = A4

    _draw_frame_and_background(c, width, height)
    address_line = f"{member.village}, {member.district or ''}, {member.state}".replace(" ,", ",")
    rule_y = _draw_letterhead(c, width, height - 20 * mm, address_line)

    title = (certificate_title or CERT_TITLES.get(certificate_type, "CERTIFICATE")).upper()
    c.setFont("CertSerif-Bold", 19)
    c.setFillColor(PANCHAYAT_700)
    c.drawCentredString(width / 2, rule_y - 13 * mm, title)

    issue_date = utcnow().strftime('%d %B %Y')
    c.setFont("CertSerif", 9.5)
    c.setFillColor(INK)
    c.drawString(25 * mm, rule_y - 24 * mm, f"Certificate No: {certificate_number}")
    c.drawRightString(width - 25 * mm, rule_y - 24 * mm, f"Date: {issue_date}")

    if certificate_type == "income":
        text = (
            f"This is to certify that Mr./Ms. {member.full_name}, "
            f"S/o / D/o {member.father_or_husband_name or '____________'}, "
            f"resident of {member.address}, {member.village}, belongs to a family "
            f"with an approximate annual income of Rs. {member.annual_income or 'N/A'}/-. "
            f"This certificate is issued for official purposes."
        )
    elif certificate_type == "residence":
        text = (
            f"This is to certify that Mr./Ms. {member.full_name} is a permanent resident of "
            f"{member.address}, {member.village}, {member.mandal or ''}, {member.district or ''}, "
            f"{member.state}. This certificate is issued for official purposes."
        )
    elif certificate_type == "birth":
        dob = member.date_of_birth.strftime("%d %B %Y") if member.date_of_birth else "N/A"
        text = (
            f"This is to certify that Mr./Ms. {member.full_name}, "
            f"S/o / D/o {member.father_or_husband_name or '____________'}, "
            f"was born on {dob} at {member.village}, {member.district or ''}, {member.state}, "
            f"as per the records available with this office."
        )
    else:
        text = (
            f"This is to certify that Mr./Ms. {member.full_name}, resident of "
            f"{member.address}, {member.village}, {member.district or ''}, {member.state}, "
            f"has been issued this {title.title()} by this office, valid as an official record."
        )

    body_y = rule_y - 38 * mm
    c.setFont("CertSerif", 11.5)
    c.setFillColor(INK)
    lines = _wrap(text, 78)
    for i, ln in enumerate(lines):
        c.drawString(28 * mm, body_y - (i * 7 * mm), ln)

    sign_y = body_y - (len(lines) * 7 * mm) - 32 * mm
    _draw_signature_block(c, width, sign_y, "Issuing Officer, JanSeva Connect", issued_by_name)
    _draw_footer(c, width, certificate_number, issue_date, f"JanSeva Connect | {title.title()} | {certificate_number} | {member.full_name} | Issued {issue_date} | By {issued_by_name}")

    c.showPage()
    c.save()
    return str(filepath)
