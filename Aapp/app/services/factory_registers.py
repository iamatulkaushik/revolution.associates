"""Factories Act 1948 register PDFs, extracted from phase3_generator.py (D5b-3c).

Pure: company + factory (or return record) in, (pdf bytes, filename) out. Raises NothingToGenerate
(same message as the old 404) when a register has no entries and FileBuildError if the PDF cannot be
built. Layouts, titles, messages and filenames are unchanged. The caller has already checked that the
factory / return belongs to the company.

compute_form34_defaults is new (Aapp's Form 34 is typed in by hand): figures taken from finalized
payroll to pre-fill the Capp form. Payroll is not split by factory, so a company with several
factories must adjust them.
"""
import logging
from decimal import Decimal

from django.db.models import Sum

from Aapp.app.services.statutory_files import FileBuildError, NothingToGenerate
from Aapp.app.services.wage_returns import FINAL, _slips

logger = logging.getLogger(__name__)


def _style():
    from Aapp.app.phase3_generator import HEADER_STYLE
    return HEADER_STYLE


def _finish(company, story, title, doc_number, what, fname):
    from Aapp.app.pdf_engine import build_pdf
    try:
        pdf = build_pdf(story, company, doc_meta={'title': title, 'doc_number': doc_number})
    except Exception as e:
        logger.exception('%s PDF failed for company=%s: %s', what, company.company_id, e)
        raise FileBuildError(f'Could not generate {what}.')
    return pdf, fname


def _register(company, f, rows, widths, title, what, prefix):
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib.units import mm
    from Aapp.app.pdf_engine import kv_table
    story = [kv_table([('Establishment Name', company.company_name), ('Factory Licence No.', f.factory_license_no)])]
    story.append(Spacer(1, 6 * mm))
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle(_style()))
    story.append(t)
    return _finish(company, story, title, f.factory_license_no, what, f'{prefix}_{f.factory_license_no}.pdf')


def build_factory_certificate_pdf(company, f):
    from Aapp.app.pdf_engine import kv_table
    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Factory Licence No.', f.factory_license_no),
        ('Occupier Name', f.occupier_name),
        ('Manager Name', f.manager_name),
        ('Factory Area (sq.m)', str(f.factory_area_sqm)),
        ('Total HP Used', str(f.total_hp_used)),
        ('Max Workers (Day)', str(f.max_workers_day)),
        ('Max Workers (Night)', str(f.max_workers_night)),
        ('Licence Expiry', f.license_expiry_date.strftime('%d %b %Y')),
    ])]
    return _finish(company, story, 'Factories Act 1948 — Registration Certificate (Form 1 & 2)',
                   f.factory_license_no, 'Factory Registration Certificate',
                   f'Factory_Registration_{f.factory_license_no}.pdf')


def build_factory_annual_return_pdf(company, rec):
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib.units import mm
    from Aapp.app.pdf_engine import kv_table, INR, section_divider
    f = rec.factory
    story = [kv_table([
        ('Establishment Name', company.company_name),
        ('Factory Licence No.', f.factory_license_no),
        ('Return Year', str(rec.year)),
    ])]
    story.append(Spacer(1, 8 * mm))
    story.append(section_divider())
    rows = [
        ['Particulars', 'Value'],
        ['Male Workers', str(rec.total_workers_male)],
        ['Female Workers', str(rec.total_workers_female)],
        ['Total Man-Days', str(rec.total_man_days)],
        ['Total Overtime Hours', str(rec.total_overtime_hours)],
        ['Total Accidents', str(rec.total_accidents)],
        ['Total Wages Paid', INR(rec.total_wages_paid)],
    ]
    t = Table(rows, colWidths=[300, 150])
    t.setStyle(TableStyle(_style() + [('ALIGN', (1, 0), (1, -1), 'RIGHT')]))
    story.append(t)
    return _finish(company, story, 'Factories Act 1948 — Annual Return (Form 34)',
                   rec.acknowledgement_no or f'FACT-AR-{rec.year}', 'Factory Annual Return',
                   f'Factory_AnnualReturn_{f.factory_license_no}_{rec.year}.pdf')


def build_whitewash_register_pdf(company, f):
    from Aapp.app.factory_act import FactoryWhitewashRegister
    records = FactoryWhitewashRegister.objects.filter(factory=f).order_by('date_done')
    if not records.exists():
        raise NothingToGenerate('No whitewash records found for this factory.')
    rows = [['Area', 'Type of Work', 'Date Done', 'Next Due', 'Contractor']]
    for r in records:
        rows.append([r.area_description[:60], r.type_of_work, r.date_done.strftime('%d-%b-%Y'),
                     r.next_due_date.strftime('%d-%b-%Y'), r.contractor_name or '—'])
    return _register(company, f, rows, [150, 90, 80, 80, 90], 'Whitewash Register (Form 7)',
                     'Whitewash register', 'Whitewash_Register')


def build_vessel_register_pdf(company, f):
    from Aapp.app.factory_act import FactoryVesselExamination
    records = FactoryVesselExamination.objects.filter(factory=f).order_by('exam_date')
    if not records.exists():
        raise NothingToGenerate('No vessel examination records found for this factory.')
    rows = [['Vessel', 'Exam Date', 'Examiner', 'Max Pressure', 'Status']]
    for r in records:
        rows.append([r.vessel_description[:60], r.exam_date.strftime('%d-%b-%Y'), r.examiner_name,
                     str(r.max_permissible_pressure), 'Fit' if r.is_fit_for_use else 'Not Fit'])
    return _register(company, f, rows, [150, 80, 110, 80, 70], 'Vessel Examination Register (Form 8)',
                     'Vessel Examination register', 'Vessel_Examination_Register')


def build_accident_register_pdf(company, f):
    from Aapp.app.factory_act import FactoryAccidentRegister
    records = (FactoryAccidentRegister.objects.filter(factory=f)
               .select_related('employee').order_by('accident_date'))
    if not records.exists():
        raise NothingToGenerate('No accident records found for this factory.')
    rows = [['Employee', 'Date', 'Nature', 'Fatal?', 'Days Lost', 'DISH Ref.']]
    for r in records:
        rows.append([r.employee.name if r.employee else '—', r.accident_date.strftime('%d-%b-%Y'),
                     r.nature_of_accident, 'Yes' if r.is_fatal else 'No', str(r.days_lost),
                     r.dish_reference_no or '—'])
    return _register(company, f, rows, [110, 75, 130, 55, 65, 75], 'Accident Register (Form 26)',
                     'Accident register', 'Accident_Register')


def compute_form34_defaults(company, factory, year, statuses=FINAL):
    """Figures from finalized payroll plus this factory's accident register, for pre-filling Form 34."""
    from Aapp.app.factory_act import FactoryAccidentRegister
    slips = _slips(company, year, statuses).select_related('employee_id')
    male, female, seen = 0, 0, set()
    for s in slips:
        if s.employee_id_id not in seen:
            seen.add(s.employee_id_id)
            if s.employee_id.gender == 'Male':
                male += 1
            elif s.employee_id.gender == 'Female':
                female += 1
    agg = slips.aggregate(days=Sum('paid_days'), ot=Sum('overtime_hours'), wages=Sum('gross_earnings'))
    return {
        'total_workers_male': male, 'total_workers_female': female,
        'total_man_days': int(agg['days'] or 0), 'total_overtime_hours': agg['ot'] or Decimal('0'),
        'total_accidents': FactoryAccidentRegister.objects.filter(factory=factory, accident_date__year=year).count(),
        'total_wages_paid': agg['wages'] or Decimal('0'),
    }
