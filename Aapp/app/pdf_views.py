"""
pdf_views.py
============
Django views — one per PDF document type.
All views return HttpResponse with PDF bytes.

Wire into Aapp/urls.py:

    from Aapp.app.pdf_views import (
        download_salary_slip, download_salary_sheet,
        download_salary_abstract, download_company_profile,
        download_letterhead_doc,
    )

    # Add inside urlpatterns:
    path('wages/<int:wages_id>/slip.pdf/',      download_salary_slip,     name='download_salary_slip'),
    path('wages/sheet/<int:month>/<int:year>/pdf/', download_salary_sheet, name='download_salary_sheet'),
    path('wages/abstract/<int:month>/<int:year>/pdf/', download_salary_abstract, name='download_salary_abstract'),
    path('company/profile.pdf/',                download_company_profile, name='download_company_profile'),
    path('letterhead/<str:doc_type>/',          download_letterhead_doc,  name='download_letterhead_doc'),
"""

import logging
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.contrib import messages

from Aapp.app.salary_pdf import (
    salary_slip_pdf, salary_sheet_pdf,
    salary_abstract_pdf, company_profile_pdf,
    letterhead_pdf,
)

logger = logging.getLogger(__name__)


def _company(request):
    """Resolve selected company from session — same helper used across Aapp."""
    from Sapp.app.company import Company
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


def _pdf_response(pdf_bytes, filename):
    """Wrap bytes in a PDF HttpResponse with correct headers."""
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Content-Length'] = len(pdf_bytes)
    return response


# ── 1. Individual Salary Slip ─────────────────────────────────────────────────

@login_required
def download_salary_slip(request, wages_id):
    """
    GET /wages/<wages_id>/slip.pdf/
    Downloads salary slip PDF for one salary_slip record (param name
    'wages_id' kept for URL/template compatibility — it's a salary_slip
    pk now, not a wages_record pk).
    Company-scoped — user can only access records for their selected company.
    """
    from Aapp.app.salary_processing import salary_slip
    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    rec = get_object_or_404(salary_slip, id=wages_id, company_id=company)

    try:
        pdf = salary_slip_pdf(rec)
    except Exception as e:
        logger.exception('salary_slip_pdf failed for wages_id=%s: %s', wages_id, e)
        raise Http404('Could not generate salary slip.')

    fname = f'Salary_Slip_{rec.employee_id.employeecode}_{rec.processing_id.month}_{rec.processing_id.year}.pdf'
    return _pdf_response(pdf, fname)


# ── 2. Monthly Salary Sheet ───────────────────────────────────────────────────

@login_required
def download_salary_sheet(request, month, year):
    """
    GET /wages/sheet/<month>/<year>/pdf/
    Downloads full salary sheet (all employees) for the selected company.
    """
    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    if not (1 <= month <= 12):
        raise Http404('Invalid month.')

    try:
        pdf = salary_sheet_pdf(company, month, year)
    except Exception as e:
        logger.exception('salary_sheet_pdf failed: %s', e)
        raise Http404('Could not generate salary sheet.')

    fname = f'Salary_Sheet_{company.company_name.replace(" ", "_")}_{month}_{year}.pdf'
    return _pdf_response(pdf, fname)


# ── 3. Salary Abstract ────────────────────────────────────────────────────────

@login_required
def download_salary_abstract(request, month, year):
    """
    GET /wages/abstract/<month>/<year>/pdf/
    Downloads department-wise salary abstract for the selected company.
    """
    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    if not (1 <= month <= 12):
        raise Http404('Invalid month.')

    try:
        pdf = salary_abstract_pdf(company, month, year)
    except Exception as e:
        logger.exception('salary_abstract_pdf failed: %s', e)
        raise Http404('Could not generate salary abstract.')

    fname = f'Salary_Abstract_{company.company_name.replace(" ", "_")}_{month}_{year}.pdf'
    return _pdf_response(pdf, fname)


# ── 4. Company Profile ────────────────────────────────────────────────────────

@login_required
def download_company_profile(request):
    """
    GET /company/profile.pdf/
    Downloads company profile PDF for the selected company.
    """
    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    try:
        pdf = company_profile_pdf(company)
    except Exception as e:
        logger.exception('company_profile_pdf failed: %s', e)
        raise Http404('Could not generate company profile.')

    fname = f'Company_Profile_{company.company_name.replace(" ", "_")}.pdf'
    return _pdf_response(pdf, fname)


# ── 5. Generic Letterhead Document ───────────────────────────────────────────

@login_required
def download_letterhead_doc(request, doc_type):
    """
    GET /letterhead/<doc_type>/
    Supported doc_type values: quotation | appointment_letter | show_cause | circular | notice

    POST body (optional JSON) allows injecting custom content_items.
    Currently ships with sensible built-in templates for each doc_type.

    Extend by adding new doc_type keys to TEMPLATES below.
    """
    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    # Built-in letterhead content templates
    today_str = __import__('datetime').date.today().strftime('%d %B %Y')

    TEMPLATES = {
        'quotation': {
            'doc_meta': {
                'title': 'Quotation',
                'doc_number': request.GET.get('ref', 'Q/2026/001'),
            },
            'content_items': [
                {'type': 'heading', 'text': 'QUOTATION'},
                {'type': 'kv', 'pairs': [
                    ('To',          request.GET.get('to', '_________________')),
                    ('Date',        today_str),
                    ('Valid Until', request.GET.get('valid_till', '_________________')),
                    ('Subject',     request.GET.get('subject', 'HRMS Services Quotation')),
                ]},
                {'type': 'spacer', 'height': 4},
                {'type': 'para', 'text': (
                    'We are pleased to submit our quotation for the services detailed below. '
                    'All prices are exclusive of applicable taxes unless stated otherwise.'
                )},
                {'type': 'spacer', 'height': 3},
                {'type': 'table',
                 'headers': ['S.No', 'Description of Service', 'Unit', 'Rate (₹)', 'Amount (₹)'],
                 'col_widths': [10, 70, 20, 28, 30],
                 'rows': [
                     ['1', 'HRMS Software Subscription (per month)', 'Month', '5,000', '5,000'],
                     ['2', 'Statutory Compliance Management',        'Month', '3,000', '3,000'],
                     ['3', 'Implementation & Training',              'One-time', '10,000', '10,000'],
                 ]},
                {'type': 'spacer', 'height': 4},
                {'type': 'kv', 'pairs': [
                    ('Sub-Total',  '₹ 18,000'),
                    ('GST @ 18%', '₹  3,240'),
                    ('TOTAL',      '₹ 21,240'),
                ]},
                {'type': 'divider'},
                {'type': 'para', 'text': (
                    '<b>Terms & Conditions:</b> Payment due within 15 days of invoice. '
                    'All disputes subject to local jurisdiction.'
                )},
                {'type': 'signature', 'labels': ['Client Acceptance', 'For Revolution Associates']},
            ],
        },

        'appointment_letter': {
            'doc_meta': {'title': 'Appointment Letter'},
            'content_items': [
                {'type': 'heading', 'text': 'APPOINTMENT LETTER'},
                {'type': 'kv', 'pairs': [
                    ('Date',        today_str),
                    ('To',          request.GET.get('emp_name', '____________________')),
                    ('Designation', request.GET.get('designation', '____________________')),
                    ('Department',  request.GET.get('department', '____________________')),
                    ('Date of Joining', request.GET.get('doj', '____________________')),
                ]},
                {'type': 'spacer', 'height': 4},
                {'type': 'para', 'text': (
                    'Dear Candidate,<br/><br/>'
                    'We are pleased to offer you the position of <b>' +
                    request.GET.get('designation', '_____') +
                    '</b> at ' + (company.company_name) +
                    '. This appointment is subject to the terms and conditions set out below.'
                )},
                {'type': 'spacer', 'height': 3},
                {'type': 'heading', 'text': 'Terms of Employment', 'level': 2},
                {'type': 'kv', 'pairs': [
                    ('Nature of Employment', 'Permanent / Probationary'),
                    ('Probation Period', '3 months'),
                    ('Working Hours', '8 hours / day, 6 days / week'),
                    ('Leave Entitlement', 'As per company policy and applicable law'),
                    ('Notice Period', '30 days'),
                ]},
                {'type': 'spacer', 'height': 3},
                {'type': 'heading', 'text': 'Compensation', 'level': 2},
                {'type': 'kv', 'pairs': [
                    ('Basic Salary',   request.GET.get('basic', '₹ ____________')),
                    ('DA',             request.GET.get('da',    '₹ ____________')),
                    ('HRA',            request.GET.get('hra',   '₹ ____________')),
                    ('Gross CTC',      request.GET.get('gross', '₹ ____________')),
                    ('EPF Deduction',  'As per EPF Act 1952 (12% of Basic)'),
                    ('ESI Deduction',  'As per ESI Act 1948 (0.75% of Gross)'),
                ]},
                {'type': 'spacer', 'height': 4},
                {'type': 'para', 'text': (
                    'Please sign and return one copy of this letter as your acceptance. '
                    'We look forward to welcoming you to our team.'
                )},
                {'type': 'signature', 'labels': ["Employee's Signature & Date", 'Authorised Signatory']},
            ],
        },

        'show_cause': {
            'doc_meta': {'title': 'Show Cause Notice'},
            'content_items': [
                {'type': 'heading', 'text': 'SHOW CAUSE NOTICE'},
                {'type': 'kv', 'pairs': [
                    ('Date',            today_str),
                    ('To',              request.GET.get('emp_name', '____________________')),
                    ('Employee Code',   request.GET.get('emp_code', '____________________')),
                    ('Designation',     request.GET.get('designation', '____________________')),
                ]},
                {'type': 'spacer', 'height': 4},
                {'type': 'para', 'text': (
                    'Dear Employee,<br/><br/>'
                    'It has been brought to our notice that you have been found to have committed the '
                    'following misconduct / breach of company policy:'
                )},
                {'type': 'spacer', 'height': 2},
                {'type': 'kv', 'pairs': [
                    ('Date of Incident', request.GET.get('incident_date', '____________________')),
                    ('Nature of Issue',  request.GET.get('issue', '____________________')),
                ]},
                {'type': 'spacer', 'height': 3},
                {'type': 'para', 'text': (
                    'You are hereby called upon to show cause within <b>48 hours</b> from the date of '
                    'this notice as to why disciplinary action should not be initiated against you. '
                    'Submit your written explanation to the HR Department.'
                )},
                {'type': 'spacer', 'height': 3},
                {'type': 'para', 'text': (
                    'Failure to respond within the stipulated time will be treated as admission of '
                    'the charges and action will be taken accordingly.'
                )},
                {'type': 'signature', 'labels': ['Employee Acknowledgement', 'HR Manager / Authorised Signatory']},
            ],
        },

        'notice': {
            'doc_meta': {'title': 'Office Notice'},
            'content_items': [
                {'type': 'heading', 'text': 'OFFICE CIRCULAR / NOTICE'},
                {'type': 'kv', 'pairs': [
                    ('Date',    today_str),
                    ('To',      'All Employees'),
                    ('Subject', request.GET.get('subject', '____________________')),
                    ('Ref. No.', request.GET.get('ref', '____________________')),
                ]},
                {'type': 'divider'},
                {'type': 'para', 'text': request.GET.get('body',
                    'This is to inform all employees that ________________________________ '
                    '________________________________________________'
                    '________________________________________________.'
                )},
                {'type': 'spacer', 'height': 6},
                {'type': 'signature', 'labels': ['', 'Authorised Signatory']},
            ],
        },
    }

    if doc_type not in TEMPLATES:
        raise Http404(f'Unknown document type: {doc_type}. Supported: {", ".join(TEMPLATES)}')

    tmpl = TEMPLATES[doc_type]
    try:
        pdf = letterhead_pdf(company, tmpl['content_items'], tmpl.get('doc_meta'))
    except Exception as e:
        logger.exception('letterhead_pdf failed for doc_type=%s: %s', doc_type, e)
        raise Http404('Could not generate document.')

    fname = f'{doc_type.replace("_", "-").title()}_{company.company_name.replace(" ", "_")}.pdf'
    return _pdf_response(pdf, fname)


# ── 6. Bulk: all wage slips as one PDF ───────────────────────────────────────

@login_required
def download_all_slips(request, month, year):
    """
    GET /wages/all-slips/<month>/<year>/pdf/
    Generates one multi-page PDF with individual salary slips for all employees.
    Useful for printing and distributing in bulk.
    """
    from reportlab.platypus import PageBreak
    from Aapp.app.salary_pdf import salary_slip_pdf
    from Aapp.app.pdf_engine import build_pdf, doc_styles, INR
    from Aapp.app.salary_pdf import _wages_qs

    company = _company(request)
    if not company:
        raise Http404('No company selected.')

    qs = _wages_qs(company, month, year)
    if not qs.exists():
        raise Http404('No wage records found for the selected period.')

    # Build one story with all slips separated by page breaks
    # Re-use salary_slip_pdf internals by generating per-record and merging bytes
    from pypdf import PdfWriter, PdfReader
    import io

    writer = PdfWriter()
    for rec in qs:
        try:
            slip_bytes = salary_slip_pdf(rec)
            reader = PdfReader(io.BytesIO(slip_bytes))
            for page in reader.pages:
                writer.add_page(page)
        except Exception as e:
            logger.warning('Skipping slip for %s: %s', rec.employee_id.employeecode, e)

    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    pdf_bytes = buf.read()

    fname = f'All_Salary_Slips_{company.company_name.replace(" ", "_")}_{month}_{year}.pdf'
    return _pdf_response(pdf_bytes, fname)
