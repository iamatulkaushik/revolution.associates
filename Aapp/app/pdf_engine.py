"""
pdf_engine.py
=============
Reusable PDF letterhead engine for Revolution Associates HRMS.

Provides:
  - `LetterheadCanvas`  — draws company header + footer on every page
  - `build_pdf()`       — builds any structured document with letterhead
  - `doc_styles()`      — consistent typography (Ubuntu-flavoured Helvetica)
  - `INR()`             — Indian currency formatter
  - Pre-built table styles for salary, report, quotation documents

Usage:
    from Aapp.app.pdf_engine import build_pdf, doc_styles, INR, table_style
    from reportlab.platypus import Paragraph, Table, Spacer

    styles = doc_styles()
    story  = [Paragraph("Hello", styles['Heading1'])]
    pdf    = build_pdf(story, company=my_company, title="My Report")
    # pdf is bytes → return as HttpResponse or attach to email
"""

import io
from datetime import date
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.colors import HexColor


# ── Brand colours (matches base.css) ─────────────────────────────────────────
NAVY   = HexColor('#1D3557')
STEEL  = HexColor('#457B9D')
TEAL   = HexColor('#A8DADC')
CORAL  = HexColor('#FF6F61')
CREAM  = HexColor('#F0F4F8')
LIGHT  = HexColor('#DDE5ED')
WHITE  = colors.white
BLACK  = colors.black
MUTED  = HexColor('#6B7C93')

# ── Page margins ──────────────────────────────────────────────────────────────
LEFT_M   = 8 * mm
RIGHT_M  = 8 * mm
TOP_M    = 38 * mm   # space for letterhead header
BOTTOM_M = 24 * mm  # space for footer

PAGE_W, PAGE_H = A4


# ── Indian currency formatter ─────────────────────────────────────────────────
def INR(amount):
    """Format number as ₹ with Indian comma grouping. Returns string."""
    try:
        amt = float(amount or 0)
    except (TypeError, ValueError):
        return '₹ 0.00'
    if amt < 0:
        return f'- ₹ {_inr_group(abs(amt))}'
    return f'₹ {_inr_group(amt)}'


def _inr_group(n):
    """1,23,456.78 Indian grouping."""
    parts = f'{n:.2f}'.split('.')
    s = parts[0]
    if len(s) <= 3:
        return f'{s}.{parts[1]}'
    last3 = s[-3:]
    rest = s[:-3]
    groups = []
    while rest:
        groups.append(rest[-2:] if len(rest) >= 2 else rest)
        rest = rest[:-2]
    return ','.join(reversed(groups)) + ',' + last3 + '.' + parts[1]


# ── Typography styles ─────────────────────────────────────────────────────────
# reportlab ships Helvetica which is metrically similar to Ubuntu — no TTF needed.
# If Ubuntu.ttf is available at FONT_PATH, register it here.

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
FONT_PATH = 'static/fonts/Ubuntu-R.ttf'
pdfmetrics.registerFont(TTFont('Ubuntu', FONT_PATH))
_basefont = 'Ubuntu'

_BASE = getSampleStyleSheet()

def doc_styles():
    """Return a dict of named ParagraphStyles for consistent document typography."""
    return {
        'Title': ParagraphStyle(
            'DocTitle', fontName=_basefont, fontSize=16,
            textColor=NAVY, alignment=TA_CENTER, spaceAfter=6,
        ),
        'Subtitle': ParagraphStyle(
            'DocSubtitle', fontName=_basefont, fontSize=11,
            textColor=STEEL, alignment=TA_CENTER, spaceAfter=4,
        ),
        'Heading1': ParagraphStyle(
            'H1', fontName=_basefont, fontSize=13,
            textColor=NAVY, spaceBefore=10, spaceAfter=4,
        ),
        'Heading2': ParagraphStyle(
            'H2', fontName=_basefont, fontSize=11,
            textColor=STEEL, spaceBefore=8, spaceAfter=3,
        ),
        'Normal': ParagraphStyle(
            'Normal', fontName=_basefont, fontSize=10,
            textColor=BLACK, alignment=TA_JUSTIFY, leading=14, spaceAfter=3,
        ),
        'Small': ParagraphStyle(
            'Small', fontName=_basefont, fontSize=8,
            textColor=MUTED, leading=11,
        ),
        'TableHeader': ParagraphStyle(
            'TH', fontName=_basefont, fontSize=9,
            textColor=WHITE, alignment=TA_CENTER,
        ),
        'TableCell': ParagraphStyle(
            'TC', fontName=_basefont, fontSize=9,
            textColor=BLACK, leading=12,
        ),
        'TableCellRight': ParagraphStyle(
            'TCR', fontName=_basefont, fontSize=9,
            textColor=BLACK, alignment=TA_RIGHT, leading=12,
        ),
        'TableCellBold': ParagraphStyle(
            'TCB', fontName=_basefont, fontSize=9,
            textColor=NAVY, leading=12,
        ),
        'Label': ParagraphStyle(
            'Label', fontName=_basefont, fontSize=9,
            textColor=MUTED, spaceAfter=1,
        ),
        'Value': ParagraphStyle(
            'Value', fontName=_basefont, fontSize=10,
            textColor=BLACK, spaceAfter=4,
        ),
        'Footer': ParagraphStyle(
            'Footer', fontName=_basefont, fontSize=8,
            textColor=MUTED, alignment=TA_CENTER,
        ),
        'AmountTotal': ParagraphStyle(
            'AmtTotal', fontName=_basefont, fontSize=11,
            textColor=NAVY, alignment=TA_RIGHT,
        ),
    }


# ── Reusable table styles ─────────────────────────────────────────────────────

def table_style(header_bg=NAVY, alt_row=True):
    """Standard data table style — navy header, optional alternating rows."""
    cmds = [
        ('BACKGROUND',   (0, 0), (-1, 0), header_bg),
        ('TEXTCOLOR',    (0, 0), (-1, 0), WHITE),
        ('FONTNAME',     (0, 0), (-1, 0), _basefont),
        ('FONTSIZE',     (0, 0), (-1, 0), 9),
        ('ALIGN',        (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME',     (0, 1), (-1, -1), _basefont),
        ('FONTSIZE',     (0, 1), (-1, -1), 9),
        ('ROWBACKGROUND', (0, 1), (-1, -1), [WHITE, CREAM]) if alt_row else ('BACKGROUND', (0, 1), (-1, -1), WHITE),
        ('GRID',         (0, 0), (-1, -1), 0.4, LIGHT),
        ('LINEBELOW',    (0, 0), (-1, 0), 1.2, NAVY),
        ('TOPPADDING',   (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 4),
        ('LEFTPADDING',  (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]
    return TableStyle(cmds)


def total_row_style():
    """Style for a totals/summary row appended to a data table."""
    return [
        ('BACKGROUND',   (0, -1), (-1, -1), NAVY),
        ('TEXTCOLOR',    (0, -1), (-1, -1), WHITE),
        ('FONTNAME',     (0, -1), (-1, -1), _basefont),
        ('LINEABOVE',    (0, -1), (-1, -1), 1.5, CORAL),
    ]


def section_divider(width=None):
    """Thin navy rule used to separate sections."""
    return HRFlowable(
        width=width or '100%', thickness=0.8,
        color=NAVY, spaceAfter=6, spaceBefore=6,
    )


# ── Letterhead canvas — draws header + footer on every page ──────────────────

class LetterheadCanvas:
    """
    Wraps reportlab canvas to draw company letterhead on every page.

    company is a dict with keys:
      company_name  (str)
      tagline       (str, optional)
      address       (str, optional)
      mobile        (str, optional)
      email         (str, optional)
      pan           (str, optional)
      gstin         (str, optional)
      cin           (str, optional)
      logo_path     (str, optional)  — absolute path to PNG/JPG logo
      registration_no (str, optional) — e.g. factory / shops-act reg no

    doc_meta is a dict:
      title         (str)
      doc_number    (str, optional)
      doc_date      (date, optional)
      ref           (str, optional)
    """

    def __init__(self, filename, company, doc_meta=None, **kwargs):
        pagesize = kwargs.pop('pagesize', A4)
        self.canvas = rl_canvas.Canvas(filename, pagesize=pagesize, **kwargs)
        self.company = company or {}
        self.doc_meta = doc_meta or {}

    def __getattr__(self, name):
        return getattr(self.canvas, name)

    def showPage(self):
        self._draw_letterhead(self.canvas._pageNumber)
        self.canvas.showPage()

    def save(self):
        # NOTE: SimpleDocTemplate calls showPage() once per completed page
        # (that draws the letterhead and does the actual page break), then
        # calls save() once at the very end. save() must only flush the
        # PDF — it must NOT draw the letterhead again, since showPage()
        # already did that for the current (last) page. Drawing here too
        # used to draw onto a fresh page that showPage() had just started,
        # producing a spurious blank trailing page on every document.
        self.canvas.save()

    def _draw_letterhead(self, page_num):
        c = self.canvas
        w, h = PAGE_W, PAGE_H

        # ── Header bar (navy gradient simulation) ──────────────────────────────
        c.setFillColor(NAVY)
        c.rect(0, h - 24 * mm, w, 24 * mm, fill=1, stroke=0)

        # Logo (if supplied)
        logo = self.company.get('logo_path')
        logo_right = LEFT_M
        if logo:
            try:
                logo_h = 20 * mm
                logo_w = logo_h  # assume square; adjust if needed
                c.drawImage(logo, LEFT_M, h - 25 * mm, width=logo_w, height=logo_h,
                            mask='auto', preserveAspectRatio=True)
                logo_right = LEFT_M + logo_w + 4 * mm
            except Exception:
                pass  # logo file missing — skip silently

        # Company name
        c.setFillColor(WHITE)
        c.setFont(_basefont, 15)
        c.drawString(logo_right, h - 8 * mm, self.company.get('company_name', 'Company Name'))

        # Tagline
        tagline = self.company.get('tagline', '')
        if tagline:
            c.setFont(_basefont, 8.5)
            c.setFillColor(TEAL)
            c.drawString(logo_right, h - 12 * mm, tagline)

        # Right side of header — contact info
        c.setFont(_basefont, 7.5)
        c.setFillColor(CREAM)
        right_x = w - RIGHT_M
        y_line = h - 9 * mm
        contact_bits = [
            ' / '.join(p for p in [self.company.get('phone', ''), self.company.get('mobile', '')] if p),
            self.company.get('email', '') + ' | ' + self.company.get('website', ''),
        ]
        for text in contact_bits:
            if text:
                c.drawRightString(right_x, y_line, str(text)[:55])
                y_line -= 5 * mm

        address = self.company.get('address', '')
        if address:
            c.setFont(_basefont, 7.5)
            c.setFillColor(CREAM)
            c.drawString(LEFT_M, h - 16 * mm, str(address)[:70])

        # ── Coral accent stripe ─────────────────────────────────────────────────
        c.setFillColor(CORAL)
        c.rect(0, h - 24.5 * mm, w, 1.5 * mm, fill=1, stroke=0)

        # ── Document meta bar (below header) ───────────────────────────────────
        doc_ref   = self.doc_meta.get('ref', '')
        doc_num   = self.doc_meta.get('doc_number', '')
        doc_title = self.doc_meta.get('title', '')
        doc_date  = self.doc_meta.get('doc_date', date.today())

        meta_y = h - 30 * mm
        meta_right_parts = []
        c.setFillColor(NAVY)
        c.setFont(_basefont, 11)
        c.drawString(LEFT_M, meta_y, doc_title)

        c.setFont(_basefont, 8.5)
        c.setFillColor(MUTED)
        if doc_ref:
            meta_right_parts.append(f'Ref: {doc_ref}')
        if doc_num:
            meta_right_parts.append(f'No: {doc_num}')
        meta_right_parts.append(f'Date: {doc_date}')
        c.drawRightString(right_x, meta_y, '   |   '.join(meta_right_parts))

        # Light rule under meta bar
        c.setStrokeColor(LIGHT)
        c.setLineWidth(0.5)
        c.line(LEFT_M, meta_y - 2 * mm, right_x, meta_y - 2 * mm)

        # ── Footer ──────────────────────────────────────────────────────────────
        footer_y = 12 * mm
        c.setStrokeColor(CORAL)
        c.setLineWidth(0.8)
        c.line(LEFT_M, footer_y + 5 * mm, right_x, footer_y + 5 * mm)

        # Registration numbers
        reg_parts = []
        if self.company.get('pan') and not self.doc_meta.get('hide_pan'):
            reg_parts.append(f'PAN: {self.company["pan"]}')
        if self.company.get('gstin'):   reg_parts.append(f'GSTIN: {self.company["gstin"]}')
        if self.company.get('cin'):     reg_parts.append(f'CIN: {self.company["cin"]}')
        if self.company.get('tan'):     reg_parts.append(f'TAN: {self.company["tan"]}')
        if self.company.get('registration_no'):
            reg_parts.append(f'Reg: {self.company["registration_no"]}')

        c.setFont(_basefont, 7)
        c.setFillColor(MUTED)
        c.drawString(LEFT_M, footer_y + 2 * mm, '   |   '.join(reg_parts))
        c.drawRightString(right_x, footer_y + 2 * mm, f'Page {page_num}')

        if not self.doc_meta.get('hide_generated_by'):
            c.setFont(_basefont, 7)
            c.drawCentredString(w / 2, footer_y - 1 * mm,
                'Generated by Revolution Associates HRMS · revolution-associates.in')


# ── Pre-printed letterhead support ──────────────────────────────────────────
#
# LetterheadCanvas above draws a full header/footer programmatically —
# use it when there's no physical letterhead, or when printing on plain
# paper. For companies that print on PRE-PRINTED stationery (paper that
# already has the logo/address/footer printed on it at a print shop),
# drawing another header on top would double up and look wrong. Two
# options for that case:
#
#   'preprinted' — draw nothing in the header/footer area, just leave
#                  the same blank margin so content doesn't collide with
#                  where the physical letterhead graphics already are.
#                  Use when printing directly onto letterhead paper.
#
#   'overlay'    — composite the generated content onto a background PDF
#                  of the actual letterhead (e.g. a scanned/exported PDF
#                  of the pre-printed page), page by page. Use when the
#                  letterhead needs to appear in an on-screen/emailed PDF
#                  rather than physical paper.

class PreprintedLetterheadCanvas:
    """
    Draws nothing — margins alone reserve space matching where the
    physical letterhead's printed header/footer already sit. Only a
    small page-number stamp is added (still needed even on pre-printed
    paper), positioned to avoid the printed footer area.

    company / doc_meta accepted for interface parity with
    LetterheadCanvas but unused for drawing — only page numbering.
    """

    def __init__(self, filename, company, doc_meta=None, **kwargs):
        pagesize = kwargs.pop('pagesize', A4)
        self.canvas = rl_canvas.Canvas(filename, pagesize=pagesize, **kwargs)
        self.company = company or {}
        self.doc_meta = doc_meta or {}

    def __getattr__(self, name):
        return getattr(self.canvas, name)

    def showPage(self):
        self._stamp_page_number(self.canvas._pageNumber)
        self.canvas.showPage()

    def save(self):
        # See LetterheadCanvas.save() note above — do not stamp again
        # here, showPage() already stamped the final page.
        self.canvas.save()

    def _stamp_page_number(self, page_num):
        c = self.canvas
        c.setFont(_basefont, 7)
        c.setFillColor(MUTED)
        # Small, unobtrusive — bottom-right, inside the reserved margin,
        # clear of typical pre-printed footer graphics/text.
        c.drawRightString(PAGE_W - RIGHT_M, 8 * mm, f'Page {page_num}')


class OverlayLetterheadCanvas:
    """
    Composites generated content onto a background PDF of the actual
    letterhead — one page of that background per output page (the last
    background page repeats if the document runs longer than the
    background PDF has pages, so multi-page documents don't run out of
    letterhead).

    background_pdf_path: path to a PDF export/scan of the pre-printed
    letterhead (a single page is normal — designed once, reused for
    every document).
    """

    def __init__(self, filename, company, doc_meta=None, background_pdf_path=None, **kwargs):
        pagesize = kwargs.pop('pagesize', A4)
        self._out_path = filename
        self.canvas = rl_canvas.Canvas(filename, pagesize=pagesize, **kwargs)
        self.company = company or {}
        self.doc_meta = doc_meta or {}
        self.background_pdf_path = background_pdf_path

    def __getattr__(self, name):
        return getattr(self.canvas, name)

    def showPage(self):
        self.canvas.showPage()

    def save(self):
        self.canvas.save()
        if self.background_pdf_path:
            self._composite_background()

    def _composite_background(self):
        """
        Runs after the base canvas is fully written — merges the
        letterhead background under every page of the just-written PDF,
        then overwrites the same path/stream with the merged result.
        """
        from pypdf import PdfReader, PdfWriter
        import io as _io

        # self._out_path may be a real path or a BytesIO buffer (both are
        # valid targets for reportlab's Canvas).
        if hasattr(self._out_path, 'seek'):
            self._out_path.seek(0)
            content_reader = PdfReader(self._out_path)
        else:
            content_reader = PdfReader(self._out_path)

        bg_reader = PdfReader(self.background_pdf_path)
        bg_pages = bg_reader.pages
        writer = PdfWriter()

        for i, page in enumerate(content_reader.pages):
            bg_page = bg_pages[min(i, len(bg_pages) - 1)]
            # Merge background UNDER the generated content — merge_page
            # composites the argument's content on top of the base page,
            # so start from a fresh copy of the background and merge the
            # generated page onto it (not the other way round).
            from pypdf import PageObject
            merged = PageObject.create_blank_page(width=bg_page.mediabox.width, height=bg_page.mediabox.height)
            merged.merge_page(bg_page)
            merged.merge_page(page)
            writer.add_page(merged)

        if hasattr(self._out_path, 'seek'):
            self._out_path.seek(0)
            self._out_path.truncate()
            writer.write(self._out_path)
            self._out_path.seek(0)
        else:
            with open(self._out_path, 'wb') as f:
                writer.write(f)



def build_pdf(story, company, doc_meta=None, filename=None,
               letterhead_mode='drawn', margins=None, background_pdf_path=None):
    """
    Build a PDF with company letterhead and return bytes.

    Args:
        story    : list of reportlab Flowable objects (Paragraphs, Tables, etc.)
        company  : dict with company fields (see LetterheadCanvas docstring)
                   OR a Company model instance (fields extracted automatically)
        doc_meta : dict with title, doc_number, doc_date, ref
        filename : internal PDF filename string (not saved to disk)

        letterhead_mode : 'drawn' (default) | 'preprinted' | 'overlay'
            'drawn'      — ReportLab paints the full header/footer itself.
                           Use for companies with no physical letterhead.
            'preprinted' — draws nothing; only reserves matching blank
                           margins + a small page-number stamp. Use when
                           printing directly onto pre-printed letterhead
                           paper — the physical stationery already has
                           the header/footer graphics.
            'overlay'    — composites content onto a background PDF of
                           the actual letterhead (pass background_pdf_path).
                           Use when the letterhead needs to appear in an
                           on-screen/emailed PDF rather than being printed
                           on physical pre-printed paper.

        margins  : optional dict overriding {'top', 'bottom', 'left', 'right'}
                   in mm — set these to match the blank space already
                   reserved on the physical letterhead stationery when
                   using 'preprinted' or 'overlay' mode. Defaults to the
                   module's standard margins if not given.

        background_pdf_path : required for letterhead_mode='overlay' —
            path to a PDF of the letterhead artwork itself.

    Returns:
        bytes — ready for HttpResponse or email attachment

    Example (pre-printed physical stationery):
        pdf_bytes = build_pdf(
            story, company=my_company_obj,
            doc_meta={'title': 'Salary Slip'},
            letterhead_mode='preprinted',
            margins={'top': 45, 'bottom': 30, 'left': 20, 'right': 20},
        )

    Example (digital letterhead overlay, e.g. for emailing):
        pdf_bytes = build_pdf(
            story, company=my_company_obj,
            doc_meta={'title': 'Salary Slip'},
            letterhead_mode='overlay',
            background_pdf_path='/path/to/company_letterhead.pdf',
        )
    """
    # Normalise company to dict
    if not isinstance(company, dict):
        company = _model_to_dict(company)

    doc_meta = doc_meta or {}
    buf = io.BytesIO()

    m = margins or {}
    top_m    = m.get('top',    TOP_M / mm)    * mm if 'top'    in m else (TOP_M    if letterhead_mode == 'drawn' else 15 * mm)
    bottom_m = m.get('bottom', BOTTOM_M / mm) * mm if 'bottom' in m else (BOTTOM_M if letterhead_mode == 'drawn' else 15 * mm)
    left_m   = m.get('left',   LEFT_M / mm)   * mm if 'left'   in m else LEFT_M
    right_m  = m.get('right',  RIGHT_M / mm)  * mm if 'right'  in m else RIGHT_M

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=left_m,
        rightMargin=right_m,
        topMargin=top_m,
        bottomMargin=bottom_m,
        title=doc_meta.get('title', 'HRMS Document'),
        author='Revolution Associates HRMS',
    )

    # Inject letterhead via canvas maker — swap implementation based on mode
    if letterhead_mode == 'preprinted':
        def canvas_maker(filename, **kwargs):
            return PreprintedLetterheadCanvas(filename, company=company, doc_meta=doc_meta, **kwargs)
    elif letterhead_mode == 'overlay':
        if not background_pdf_path:
            raise ValueError("letterhead_mode='overlay' requires background_pdf_path")
        def canvas_maker(filename, **kwargs):
            return OverlayLetterheadCanvas(
                filename, company=company, doc_meta=doc_meta,
                background_pdf_path=background_pdf_path, **kwargs
            )
    else:  # 'drawn' — existing behaviour, unchanged
        def canvas_maker(filename, **kwargs):
            return LetterheadCanvas(filename, company=company, doc_meta=doc_meta, **kwargs)

    doc.build(story, canvasmaker=canvas_maker)
    buf.seek(0)
    return buf.read()


def _model_to_dict(company):
    """Extract standard fields from a Company model instance."""
    def g(field, default=''):
        val = getattr(company, field, None)
        if val is None or str(val).strip().lower() == 'none':
            return default
        return val

    state_name = getattr(company.state_id, 'name', '') if getattr(company, 'state_id', None) else ''
    district_name = getattr(company.district_id, 'name', '') if getattr(company, 'district_id', None) else ''
    state_name = state_name.title() if state_name else ''
    district_name = district_name.title() if district_name else ''

    address_parts = [
        g('address1'), g('address2'), g('address3'),
        district_name, state_name,
    ]
    address_line = ', '.join(p for p in address_parts if p)
    if g('pin'):
        address_line = f"{address_line} - {g('pin')}"

    return {
        'company_name':    g('company_name'),
        'tagline':         g('tagline1') or g('company_tagline'),
        'address':         address_line,
        'mobile':          g('mobile') or g('phone'),
        'phone':           g('phone') or g('phone2'),
        'email':           g('email1') or g('email'),
        'website':         g('website'),
        'pan':             g('pan'),
        'gstin':           g('gstin') or g('gst_no'),
        'cin':             g('cin'),
        'tan':             g('tan'),
        'registration_no': g('registration_number') or g('factory_license_no'),
        'logo_path':       g('logo_path') or g('logo'),
    }


# ── Convenience: two-column key-value table (for slips, profiles) ────────────

def kv_table(pairs, col_widths=None, label_color=NAVY):
    """
    Build a two-column label:value table.
    pairs = [('Label', 'Value'), ...]
    """
    avail = PAGE_W - LEFT_M - RIGHT_M
    col_widths = col_widths or [avail * 0.38, avail * 0.62]
    styles = doc_styles()
    data = [
        [Paragraph(f'<b>{k}</b>', styles['Label']),
         Paragraph(str(v or '—'), styles['Value'])]
        for k, v in pairs
    ]
    ts = TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',   (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW',    (0, 0), (-1, -1), 0.3, LIGHT),
    ])
    return Table(data, colWidths=col_widths, style=ts)


# ── Convenience: amount words (Indian) ───────────────────────────────────────

_ONES = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
         'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen',
         'Seventeen', 'Eighteen', 'Nineteen']
_TENS = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']


def _below_hundred(n):
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (' ' + _ONES[n % 10] if n % 10 else '')).strip()


def amount_in_words(amount):
    """Convert rupee amount to words. E.g. 12345.50 → 'Rupees Twelve Thousand Three Hundred Forty Five and Fifty Paise Only'"""
    try:
        amount = round(float(amount or 0), 2)
    except (TypeError, ValueError):
        return 'Rupees Zero Only'

    rupees = int(amount)
    paise  = round((amount - rupees) * 100)

    def _convert(n):
        if n == 0:   return ''
        if n < 100:  return _below_hundred(n)
        if n < 1000: return _ones[n // 100] + ' Hundred' + (' ' + _convert(n % 100) if n % 100 else '')
        if n < 1_00_000:   return _convert(n // 1000) + ' Thousand' + (' ' + _convert(n % 1000) if n % 1000 else '')
        if n < 1_00_00_000: return _convert(n // 1_00_000) + ' Lakh' + (' ' + _convert(n % 1_00_000) if n % 1_00_000 else '')
        return _convert(n // 1_00_00_000) + ' Crore' + (' ' + _convert(n % 1_00_00_000) if n % 1_00_00_000 else '')

    _ones = _ONES  # local ref
    r_words = _convert(rupees) or 'Zero'
    p_words = _convert(paise)
    result = f'Rupees {r_words}'
    if paise:
        result += f' and {p_words} Paise'
    return result + ' Only'