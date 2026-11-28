"""Minimum Wages Form V and Payment of Wages Form IV annual returns, extracted from
wage_compliance.py, phase2_generator.py and pow_generator.py (D5b-3a).

Pure: company / return record in, totals or (pdf bytes, filename) out. PDF layout, titles and
filenames are unchanged.

`statuses` on the compute functions: None (the Aapp behaviour) counts every salary batch of the
year, whatever its status. Capp passes ('APPROVED', 'PAID') so that only finalized payroll goes into
a statutory return; fines, deductions and overtime are then limited to those same months.

The old Aapp helpers carried a stray @login_required, which made calling them with a company
crash; the extracted functions are plain, so the Aapp "generate return" views now work.
"""
import logging
from decimal import Decimal

from django.db.models import Sum

from Aapp.app.services.statutory_files import FileBuildError, _slug

logger = logging.getLogger(__name__)
FINAL = ('APPROVED', 'PAID')


def _slips(company, year, statuses):
    from Aapp.app.salary_processing import salary_slip
    qs = salary_slip.objects.filter(company_id=company, processing_id__year=year)
    if statuses is not None:
        qs = qs.filter(processing_id__status__in=statuses)
    return qs


def _months(company, year, statuses):
    if statuses is None:
        return None
    from Aapp.app.salary_processing import salary_processing
    return set(salary_processing.objects.filter(
        company_id=company, year=year, status__in=statuses).values_list('month', flat=True))


def _only(qs, field, months):
    return qs if months is None else qs.filter(**{f'{field}__in': months})


def _fines_and_deductions(company, year, months):
    from Aapp.app.wages import wages_fine, wages_deduction
    fines = _only(wages_fine.objects.filter(company=company, salary_year=year),
                  'salary_month', months).aggregate(t=Sum('fine_amount'))['t'] or Decimal('0')
    deds = _only(wages_deduction.objects.filter(company=company, salary_year=year),
                 'salary_month', months).aggregate(t=Sum('deduction_amount'))['t'] or Decimal('0')
    return fines, deds


def compute_minwages_totals(company, year, statuses=None):
    from Aapp.app.attandance import MinimumWagesOvertimeRegister
    slips = _slips(company, year, statuses).select_related('employee_id')
    male = female = 0
    total_wages = Decimal('0')
    seen = set()
    for s in slips:
        total_wages += Decimal(s.gross_earnings or 0)
        if s.employee_id_id not in seen:
            seen.add(s.employee_id_id)
            if s.employee_id.gender == 'Male':
                male += 1
            elif s.employee_id.gender == 'Female':
                female += 1
    months = _months(company, year, statuses)
    ot = _only(MinimumWagesOvertimeRegister.objects.filter(
        attendance__companyid=company, attendance__salary_year=year), 'attendance__salary_month', months)
    ot_hours = sum((r.overtime_hours for r in ot), Decimal('0'))
    ot_wages = sum((r.ot_wages_paid for r in ot), Decimal('0'))
    fines, deds = _fines_and_deductions(company, year, months)
    return {
        'total_employees_male': male, 'total_employees_female': female,
        'total_wages_paid': total_wages, 'total_ot_hours': int(ot_hours),
        'total_ot_wages': ot_wages, 'total_fines_imposed': fines, 'total_deductions': deds,
    }


def compute_pow_totals(company, year, statuses=None):
    slips = _slips(company, year, statuses).select_related('employee_id')
    total_wages = sum((Decimal(s.gross_earnings or 0) for s in slips), Decimal('0'))
    total_employed = slips.values('employee_id').distinct().count()
    fines, deds = _fines_and_deductions(company, year, _months(company, year, statuses))
    return {
        'total_employed': total_employed, 'total_wages_paid': total_wages,
        'total_fines_imposed': fines, 'total_fines_realised': fines, 'total_deductions': deds,
    }


def build_minwages_return_pdf(company, rec):
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib.units import mm
    from Aapp.app.pdf_engine import build_pdf, kv_table, INR, section_divider
    from Aapp.app.phase2_generator import HEADER_STYLE
    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Return Year', str(rec.year)),
        ('Category of Work', rec.category_of_work),
        ('Employees (M/F)', f'{rec.total_employees_male} / {rec.total_employees_female}'),
    ])]
    story.append(Spacer(1, 8 * mm))
    story.append(section_divider())
    rows = [
        ['Particulars', 'Amount (₹)'],
        ['Min Wage Rate — Unskilled', INR(rec.min_wage_rate_unskilled)],
        ['Min Wage Rate — Semi-skilled', INR(rec.min_wage_rate_semiskilled)],
        ['Min Wage Rate — Skilled', INR(rec.min_wage_rate_skilled)],
        ['Total Wages Paid', INR(rec.total_wages_paid)],
        ['Total OT Hours', str(rec.total_ot_hours)],
        ['Total OT Wages', INR(rec.total_ot_wages)],
        ['Total Fines Imposed', INR(rec.total_fines_imposed)],
        ['Total Deductions', INR(rec.total_deductions)],
    ]
    t = Table(rows, colWidths=[300, 150])
    t.setStyle(TableStyle(HEADER_STYLE + [('ALIGN', (1, 0), (1, -1), 'RIGHT')]))
    story.append(t)
    try:
        pdf = build_pdf(story, company, doc_meta={'title': 'Minimum Wages Act — Annual Return (Form V)',
                                                    'doc_number': rec.acknowledgement_no or f'MW-{rec.year}'})
    except Exception as e:
        logger.exception('Min wages return PDF failed for return_id=%s: %s', rec.return_id, e)
        raise FileBuildError('Could not generate Minimum Wages return.')
    return pdf, f'MinWages_Form_V_{_slug(company)}_{rec.year}.pdf'


def build_pow_return_pdf(company, rec):
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from Aapp.app.pdf_engine import build_pdf, kv_table, INR, section_divider
    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Return Year', str(rec.year)),
        ('Total Persons Employed', str(rec.total_employed)),
        ('Wage Period', rec.get_wage_period_display()),
        ('Mode of Payment', rec.get_payment_mode_display()),
    ])]
    story.append(Spacer(1, 8 * mm))
    story.append(section_divider())
    rows = [
        ['Particulars', 'Amount (₹)'],
        ['Total Wages Paid', INR(rec.total_wages_paid)],
        ['Total Fines Imposed', INR(rec.total_fines_imposed)],
        ['Total Fines Realised', INR(rec.total_fines_realised)],
        ['Total Deductions (other than fines)', INR(rec.total_deductions)],
    ]
    t = Table(rows, colWidths=[300, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0B2545')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': 'Payment of Wages Act — Annual Return (Form IV)',
            'doc_number': rec.acknowledgement_no or f'POW-{rec.year}'})
    except Exception as e:
        logger.exception('POW return PDF failed for return_id=%s: %s', rec.return_id, e)
        raise FileBuildError('Could not generate Payment of Wages return.')
    return pdf, f'POW_Form_IV_{_slug(company)}_{rec.year}.pdf'
