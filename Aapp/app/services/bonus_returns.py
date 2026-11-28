"""Payment of Bonus Act builders, extracted from bonus.py and phase2_generator.py (D5b-3b).

Form D annual return totals and PDF, Form B set-on/set-off PDF and the Form C monthly register PDF.
Pure: company / record in, totals or (pdf bytes, filename) out. Layout, titles, messages and
filenames are unchanged.

`statuses` / `paid_only` on compute_bonus_return_totals: the defaults (None, False) are the Aapp
behaviour, which counts every salary batch and every bonus record of the year. Capp passes
('APPROVED', 'PAID') and paid_only=True, so Form D reflects finalized payroll and bonus actually paid.

The old Aapp helper carried @login_required and @require_feature, which made calling it with a
company crash; the extracted function is plain, so the Aapp "generate return" view now works.
"""
import calendar
import logging
from decimal import Decimal

from django.db.models import Sum

from Aapp.app.services.statutory_files import FileBuildError, NothingToGenerate, _slug
from Aapp.app.services.wage_returns import _slips

logger = logging.getLogger(__name__)


def compute_bonus_return_totals(company, year, statuses=None, paid_only=False):
    from Aapp.app.bonus import bonus_record
    slips = _slips(company, year, statuses)
    total_employees = slips.values('employee_id').distinct().count()
    total_wages = slips.aggregate(t=Sum('gross_earnings'))['t'] or Decimal('0')
    records = bonus_record.objects.filter(company=company, salary_year=year)
    if paid_only:
        records = records.filter(is_paid=True)
    total_bonus_paid = records.aggregate(t=Sum('total_bonus'))['t'] or Decimal('0')
    bonus_percentage = ((total_bonus_paid / total_wages * 100).quantize(Decimal('0.01'))
                        if total_wages else Decimal('0'))
    # Not clamped to the statutory 8.33%-20% band: out-of-band values are shown, not hidden.
    return {'total_employees': total_employees, 'total_wages': total_wages,
            'total_bonus_paid': total_bonus_paid, 'bonus_percentage': bonus_percentage}


def _summary_pdf(company, header, rows, title, doc_number, what, file_prefix, year):
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib.units import mm
    from Aapp.app.pdf_engine import build_pdf, kv_table, section_divider
    from Aapp.app.phase2_generator import HEADER_STYLE
    story = [kv_table(header)]
    story.append(Spacer(1, 8 * mm))
    story.append(section_divider())
    t = Table(rows, colWidths=[300, 150])
    t.setStyle(TableStyle(HEADER_STYLE + [('ALIGN', (1, 0), (1, -1), 'RIGHT')]))
    story.append(t)
    try:
        pdf = build_pdf(story, company, doc_meta={'title': title, 'doc_number': doc_number})
    except Exception as e:
        logger.exception('%s PDF failed for company=%s year=%s: %s', what, company.company_id, year, e)
        raise FileBuildError(f'Could not generate {what}.')
    return pdf, f'{file_prefix}_{_slug(company)}_{year}.pdf'


def build_bonus_return_pdf(company, rec):
    from Aapp.app.pdf_engine import INR
    header = [
        ('Establishment Name', company.company_name),
        ('Return Year', str(rec.year)),
        ('Total Employees', str(rec.total_employees)),
        ('Payment Date', rec.payment_date.strftime('%d %b %Y') if rec.payment_date else '—'),
    ]
    rows = [
        ['Particulars', 'Amount (₹)'],
        ['Total Wages (for bonus calc)', INR(rec.total_wages)],
        ['Allocable Surplus', INR(rec.allocable_surplus)],
        ['Bonus Percentage', f'{rec.bonus_percentage}%'],
        ['Total Bonus Paid', INR(rec.total_bonus_paid)],
    ]
    return _summary_pdf(company, header, rows, 'Payment of Bonus Act — Annual Return (Form D)',
                        rec.acknowledgement_no or f'BONUS-{rec.year}', 'Bonus annual return',
                        'Bonus_Form_D', rec.year)


def build_set_on_set_off_pdf(company, rec):
    from Aapp.app.pdf_engine import INR
    header = [('Establishment Name', company.company_name), ('Accounting Year', str(rec.year))]
    rows = [
        ['Particulars', 'Amount (₹)'],
        ['Allocable Surplus', INR(rec.allocable_surplus)],
        ['Total Wages for Bonus', INR(rec.total_wages_for_bonus)],
        ['Minimum Bonus (8.33%)', INR(rec.min_bonus_amount)],
        ['Maximum Bonus (20%)', INR(rec.max_bonus_amount)],
        ['Bonus Paid', INR(rec.bonus_paid)],
        ['Set-On Amount', INR(rec.set_on_amount)],
        ['Set-Off Amount', INR(rec.set_off_amount)],
        ['Cumulative Set-On Balance', INR(rec.cumulative_set_on)],
    ]
    return _summary_pdf(company, header, rows, 'Payment of Bonus Act — Set-On/Set-Off Register (Form B)',
                        f'SETONOFF-{rec.year}', 'Set-On/Set-Off register', 'Bonus_FormB_SetOnOff', rec.year)


def build_bonus_register_pdf(company, month, year):
    from Aapp.app.bonus import bonus_record
    from Aapp.app.pdf_engine import INR
    from Aapp.app.services.registers import _finish
    records = (bonus_record.objects.filter(company=company, salary_month=month, salary_year=year)
               .select_related('employee').order_by('employee__name'))
    if not records.exists():
        raise NothingToGenerate(f'No bonus records found for {calendar.month_name[month]} {year}.')
    rows = [['Employee', 'Basic Bonus', 'Perf. Bonus', 'Festival Bonus', 'Other', 'Total', 'Paid']]
    total = 0
    for b in records:
        rows.append([b.employee.name, INR(b.basic_bonus), INR(b.performance_bonus),
                     INR(b.festival_bonus), INR(b.other_bonus), INR(b.total_bonus),
                     'Yes' if b.is_paid else 'No'])
        total += b.total_bonus
    rows.append(['', '', '', '', 'TOTAL', INR(total), ''])
    return _finish(company, month, year, rows, [110, 75, 75, 80, 65, 80, 45], ((1, 0), (5, -1)),
                   'Bonus Register (Form C)', 'BONUS-REG', 'Bonus register', 'Bonus_Register')
