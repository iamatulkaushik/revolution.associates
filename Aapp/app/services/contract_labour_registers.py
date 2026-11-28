"""Contract Labour (Regulation & Abolition) Act 1970 PDFs, extracted from phase4_generator.py (D5b-3d).

Pure: company + record in, (pdf bytes, filename) out. Raises NothingToGenerate (same message as the
old 404) for a contractor with no payments, and FileBuildError if a PDF cannot be built. Layouts,
titles, doc numbers, messages and filenames are unchanged. The caller has already checked that the
record belongs to the company.

compute_cl_half_year_totals is new (Aapp's Form 20(CL) is typed in by hand): figures for one
contractor and half year from finalized payroll of the workers deployed under that contractor.
"""
import logging
from decimal import Decimal

from django.db.models import Q, Sum

from Aapp.app.services.statutory_files import FileBuildError, NothingToGenerate
from Aapp.app.services.wage_returns import FINAL

logger = logging.getLogger(__name__)

HALF_MONTHS = {'jan_jun': (1, 2, 3, 4, 5, 6), 'jul_dec': (7, 8, 9, 10, 11, 12)}


def _style():
    from Aapp.app.phase4_generator import HEADER_STYLE
    return HEADER_STYLE


def _finish(company, story, title, doc_number, what, fname):
    from Aapp.app.pdf_engine import build_pdf
    try:
        pdf = build_pdf(story, company, doc_meta={'title': title, 'doc_number': doc_number})
    except Exception as e:
        logger.exception('%s PDF failed for company=%s: %s', what, company.company_id, e)
        raise FileBuildError(f'Could not generate {what}.')
    return pdf, fname


def _under(name):
    return name.replace(' ', '_')


def build_cl_registration_pdf(company, rec):
    from Aapp.app.pdf_engine import kv_table
    story = [kv_table([
        ('Establishment Name', rec.establishment_name),
        ('Registration Certificate No.', rec.registration_cert_no or '—'),
        ('Registration Date', rec.registration_date.strftime('%d %b %Y') if rec.registration_date else '—'),
        ('Registering Authority', rec.registration_authority or '—'),
        ('Nature of Work', rec.nature_of_work),
        ('Max Contract Workers', str(rec.max_contract_workers)),
        ('Status', 'Active' if rec.is_active else 'Inactive'),
    ])]
    return _finish(company, story, 'Contract Labour (R&A) Act 1970 — Registration Certificate (Form I & II)',
                   rec.registration_cert_no or f'CL-REG-{rec.reg_id}', 'CL Registration Certificate',
                   f'CL_Registration_{_under(company.company_name)}_{rec.reg_id}.pdf')


def build_employment_card_pdf(company, card):
    from Aapp.app.pdf_engine import kv_table, INR
    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Contractor', card.contractor.contractor_name),
        ('Worker Name', card.employee.name),
        ('Employee Code', card.employee.employeecode),
        ('Card No.', card.card_number or '—'),
        ('Token No.', card.token_number or '—'),
        ('Work Description', card.work_description),
        ('Work Site', card.work_site),
        ('Wage Rate', INR(card.wage_rate)),
        ('Issue Date', card.issue_date.strftime('%d %b %Y')),
        ('Validity Date', card.validity_date.strftime('%d %b %Y') if card.validity_date else '—'),
    ])]
    return _finish(company, story, 'Contract Labour (R&A) Act 1970 — Employment Card (Form XIII)',
                   card.card_number or f'CL-CARD-{card.card_id}', 'Employment Card',
                   f'Employment_Card_{card.employee.employeecode}.pdf')


def build_service_certificate_pdf(company, cert):
    from Aapp.app.pdf_engine import kv_table, INR
    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Contractor', cert.contractor.contractor_name),
        ('Worker Name', cert.employee.name),
        ('Employee Code', cert.employee.employeecode),
        ('Work Description', cert.work_description),
        ('Work Site', cert.work_site),
        ('Date of Employment', cert.date_of_employment.strftime('%d %b %Y')),
        ('Date of Termination', cert.date_of_termination.strftime('%d %b %Y')),
        ('Reason for Termination', cert.reason_for_termination or '—'),
        ('Last Wage Paid', INR(cert.last_wage_paid)),
        ('Certificate Date', cert.certificate_date.strftime('%d %b %Y')),
    ])]
    return _finish(company, story, 'Contract Labour (R&A) Act 1970 — Service Certificate (Form XIV)',
                   f'CL-CERT-{cert.cert_id}', 'Service Certificate',
                   f'Service_Certificate_{cert.employee.employeecode}.pdf')


def build_cl_return_pdf(company, rec):
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib.units import mm
    from Aapp.app.pdf_engine import kv_table, INR, section_divider
    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Contractor', rec.contractor.contractor_name),
        ('Period', f'{rec.get_half_year_display()} {rec.year}'),
    ])]
    story.append(Spacer(1, 8 * mm))
    story.append(section_divider())
    rows = [
        ['Particulars', 'Value'],
        ['Total Workers Employed', str(rec.total_workers_employed)],
        ['Total Man-Days', str(rec.total_man_days)],
        ['Total Wages Paid', INR(rec.total_wages_paid)],
        ['Total Overtime Hours', str(rec.total_overtime_hours)],
        ['Total Overtime Wages', INR(rec.total_overtime_wages)],
    ]
    t = Table(rows, colWidths=[300, 150])
    t.setStyle(TableStyle(_style() + [('ALIGN', (1, 0), (1, -1), 'RIGHT')]))
    story.append(t)
    return _finish(company, story, 'Contract Labour (R&A) Act 1970 — Half-Yearly Return (Form 20-CL)',
                   rec.acknowledgement_no or f'CL-RET-{rec.year}-{rec.half_year}',
                   'Contract Labour Half-Yearly Return',
                   f'CL_Return_{_under(rec.contractor.contractor_name)}_{rec.year}_{rec.half_year}.pdf')


def build_contractor_payment_register_pdf(company, c):
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib.units import mm
    from Aapp.app.contractor import contractor_payment
    from Aapp.app.pdf_engine import kv_table, INR, _basefont_bold
    records = contractor_payment.objects.filter(contractor=c).order_by('salary_year', 'salary_month')
    if not records.exists():
        raise NothingToGenerate('No payment records found for this contractor.')
    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Contractor', c.contractor_name),
        ('Licence No.', c.contractor_license_no or '—'),
    ])]
    story.append(Spacer(1, 6 * mm))
    rows = [['Month/Year', 'Amount (₹)', 'Payment Date', 'Reference', 'Remarks']]
    total = 0
    for p in records:
        rows.append([f'{p.salary_month}/{p.salary_year}', INR(p.payment_amount),
                     p.payment_date.strftime('%d-%b-%Y'), p.payment_reference or '—',
                     (p.remarks or '—')[:40]])
        total += p.payment_amount
    rows.append(['TOTAL', INR(total), '', '', ''])
    t = Table(rows, colWidths=[80, 90, 90, 100, 130])
    t.setStyle(TableStyle(_style() + [
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), _basefont_bold),
    ]))
    story.append(t)
    return _finish(company, story, 'Contractor Payment Register', f'CTR-PAY-{c.contractor_id}',
                   'Contractor Payment register',
                   f'Contractor_Payment_Register_{_under(c.contractor_name)}.pdf')


def compute_cl_half_year_totals(company, contractor, year, half_year, statuses=FINAL):
    """Form 20(CL) figures for one contractor and half year from finalized payroll.

    Workers are those deployed under the contractor at any time in the half year (contractor_worker
    rows); only their salary slips for the half year's months count.
    """
    from datetime import date
    from Aapp.app.contractor import contractor_worker
    from Aapp.app.salary_processing import salary_slip
    months = HALF_MONTHS[half_year]
    start, end = date(year, months[0], 1), date(year, months[-1], 28)
    emp_ids = contractor_worker.objects.filter(contractor=contractor, company=company).filter(
        deployment_start__lte=end).filter(
        Q(deployment_end__isnull=True) | Q(deployment_end__gte=start)).values_list('employee_id', flat=True)
    slips = salary_slip.objects.filter(
        company_id=company, processing_id__year=year, processing_id__month__in=months,
        employee_id__in=list(emp_ids))
    if statuses is not None:
        slips = slips.filter(processing_id__status__in=statuses)
    agg = slips.aggregate(days=Sum('paid_days'), wages=Sum('gross_earnings'),
                          oth=Sum('overtime_hours'), otw=Sum('overtime_amount'))
    return {
        'total_workers_employed': slips.values('employee_id').distinct().count(),
        'total_man_days': int(agg['days'] or 0),
        'total_wages_paid': agg['wages'] or Decimal('0'),
        'total_overtime_hours': int(agg['oth'] or 0),
        'total_overtime_wages': agg['otw'] or Decimal('0'),
    }
