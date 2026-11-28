"""Nomination, family-declaration and leave register builders, extracted from phase5_generator.py
and phase3_generator.py (D5b-2).

Pure: company in, (pdf bytes, filename) out. Raises NothingToGenerate when there are no records and
FileBuildError when the PDF cannot be built. Tables, titles, messages and filenames are unchanged.
"""
import logging

from Aapp.app.services.statutory_files import FileBuildError, NothingToGenerate, _slug

logger = logging.getLogger(__name__)


def _render(company, rows, widths, header_style, extra_style, title, doc_prefix, what, file_prefix):
    from reportlab.platypus import Table, TableStyle, Spacer
    from reportlab.lib.units import mm
    from Aapp.app.pdf_engine import build_pdf, kv_table
    story = [kv_table([('Establishment Name', company.company_name)])]
    story.append(Spacer(1, 6 * mm))
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle(header_style + extra_style))
    story.append(t)
    try:
        pdf = build_pdf(story, company, doc_meta={'title': title,
                                                    'doc_number': f'{doc_prefix}-{company.company_id}'})
    except Exception as e:
        logger.exception('%s PDF failed for company=%s: %s', what, company.company_id, e)
        raise FileBuildError(f'Could not generate {what}.')
    return pdf, f'{file_prefix}_{_slug(company)}.pdf'


def _p5_style():
    from Aapp.app.phase5_generator import HEADER_STYLE
    return HEADER_STYLE


def build_gratuity_nominee_register_pdf(company):
    from Aapp.app.gratuity import gratuity_nominee
    records = (gratuity_nominee.objects.filter(company=company)
               .select_related('employee').order_by('employee__name'))
    if not records.exists():
        raise NothingToGenerate('No gratuity nominees registered.')
    rows = [['Employee', 'Nominee', 'Relationship', 'Share %', 'Aadhaar', 'Minor?']]
    for n in records:
        rows.append([n.employee.name, n.nominee_name, n.get_relationship_display(),
                     f'{n.share_percent}%', n.aadhar_number or '—', 'Yes' if n.is_minor else 'No'])
    return _render(company, rows, [100, 100, 90, 55, 90, 50], _p5_style(), [],
                   'Gratuity Act 1972 — Nominee Register (Form F)', 'GRAT-NOM',
                   'Gratuity Nominee register', 'Gratuity_Nominee_Register')


def build_epf_nomination_register_pdf(company):
    from Aapp.app.epf_esi import EpfNomination
    records = (EpfNomination.objects.filter(company=company)
               .select_related('employee').order_by('employee__name'))
    if not records.exists():
        raise NothingToGenerate('No EPF nominations recorded.')
    rows = [['Employee', 'Nominee', 'Relationship', 'Share %', 'EPS Nominee?', 'Nomination Date']]
    for n in records:
        rows.append([n.employee.employeecode, n.nominee_name, n.get_relationship_display(),
                     f'{n.share_percent}%', 'Yes' if n.is_eps_nominee else 'No',
                     n.nomination_date.strftime('%d-%b-%Y')])
    return _render(company, rows, [80, 100, 90, 55, 80, 90], _p5_style(), [],
                   'EPF Nomination & Declaration Register (Form 2)', 'EPF-NOM',
                   'EPF Nomination register', 'EPF_Nomination_Register')


def build_esi_family_register_pdf(company):
    from Aapp.app.epf_esi import EsiFamilyMember
    records = (EsiFamilyMember.objects.filter(company=company)
               .select_related('employee').order_by('employee__name'))
    if not records.exists():
        raise NothingToGenerate('No ESI family members declared.')
    rows = [['Employee', 'Member Name', 'Relationship', 'DOB', 'Status']]
    for m in records:
        status = 'Active' if not m.date_removed else f'Removed {m.date_removed.strftime("%d-%b-%Y")}'
        rows.append([m.employee.employeecode, m.member_name, m.get_relationship_display(),
                     m.date_of_birth.strftime('%d-%b-%Y') if m.date_of_birth else '—', status])
    return _render(company, rows, [80, 110, 90, 80, 120], _p5_style(), [],
                   'ESI Family Declaration Register (Form 1A)', 'ESI-FAM',
                   'ESI Family register', 'ESI_Family_Register')


def build_leave_wages_register_pdf(company):
    from Aapp.app.factory_act import LeaveWithWagesRegister
    from Aapp.app.pdf_engine import INR
    from Aapp.app.phase3_generator import HEADER_STYLE
    records = (LeaveWithWagesRegister.objects.filter(employee__CompanyID=company)
               .select_related('employee').order_by('-year', 'employee__name'))
    if not records.exists():
        raise NothingToGenerate('No leave-with-wages records found for this company.')
    rows = [['Employee', 'Year', 'Opening', 'Earned', 'Availed', 'Lapsed', 'Encashed', 'Amount (₹)']]
    for r in records:
        rows.append([r.employee.name, str(r.year), str(r.opening_balance), str(r.leave_earned),
                     str(r.leave_availed), str(r.leave_lapsed), str(r.leave_encashed), INR(r.encashment_amount)])
    return _render(company, rows, [100, 45, 60, 60, 60, 60, 65, 75], HEADER_STYLE,
                   [('ALIGN', (2, 0), (-1, -1), 'RIGHT')],
                   'Leave With Wages Register (Form 15)', 'LWW',
                   'Leave With Wages register', 'Leave_With_Wages_Register')
