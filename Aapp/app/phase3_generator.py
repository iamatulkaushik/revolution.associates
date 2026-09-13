"""
phase3_generator.py
====================
Phase 3 — Factories Act 1948 register PDFs, all factory-scoped
(not month/year scoped, unlike Phase 1/2). Two shapes:

  A) Single-record documents:
     - Factory Registration Certificate (Form 1 & 2) -> download_factory_registration_cert
     - Annual Return (Form 34)                        -> download_factory_annual_return

  B) Full-history registers, one factory's entire log:
     - Whitewash Register (Form 7)                    -> download_whitewash_register
     - Vessel Examination Register (Form 8)            -> download_vessel_examination_register
     - Accident Register (Form 26)                     -> download_accident_register
     - Leave With Wages Register (Form 15)              -> download_leave_wages_register
       (company-scoped, not factory-scoped — model has no FK to factory)

Wire into Aapp/urls.py:

    from Aapp.app.phase3_generator import (
        download_factory_registration_cert, download_factory_annual_return,
        download_whitewash_register, download_vessel_examination_register,
        download_accident_register, download_leave_wages_register,
    )

    path('factory/<int:factory_id>/certificate/download/', download_factory_registration_cert, name='download_factory_registration_cert'),
    path('factory/annual-return/<int:return_id>/download/', download_factory_annual_return, name='download_factory_annual_return'),
    path('factory/<int:factory_id>/whitewash/download/', download_whitewash_register, name='download_whitewash_register'),
    path('factory/<int:factory_id>/vessel/download/', download_vessel_examination_register, name='download_vessel_examination_register'),
    path('factory/<int:factory_id>/accident/download/', download_accident_register, name='download_accident_register'),
    path('factory/leave-wages/download/', download_leave_wages_register, name='download_leave_wages_register'),

Add corresponding row/nav links in list_factory_registration, list_annual_return,
list_whitewash_register, list_vessel_examination, list_accident_register,
list_leave_wages_register.
"""

import logging
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from reportlab.platypus import Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.lib.units import mm

from Aapp.app.pdf_engine import build_pdf, kv_table, INR, section_divider

logger = logging.getLogger(__name__)

HEADER_STYLE = [
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0B2545')),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ('TOPPADDING', (0, 0), (-1, -1), 5),
]


def _company(request):
    from Sapp.app.company import Company
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── A) Factory Registration Certificate (Form 1 & 2) ─────────────────────────

@login_required
def download_factory_registration_cert(request, factory_id):
    from Aapp.app.factory_act import FactoryRegistration
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    f = get_object_or_404(FactoryRegistration, factory_id=factory_id, company=company)

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

    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': 'Factories Act 1948 — Registration Certificate (Form 1 & 2)',
            'doc_number': f.factory_license_no,
        })
    except Exception as e:
        logger.exception('Factory registration cert PDF failed for factory_id=%s: %s', factory_id, e)
        raise Http404('Could not generate Factory Registration Certificate.')

    fname = f'Factory_Registration_{f.factory_license_no}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── A) Factory Annual Return (Form 34) ───────────────────────────────────────

@login_required
def download_factory_annual_return(request, return_id):
    from Aapp.app.factory_act import FactoryAnnualReturn
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    rec = get_object_or_404(FactoryAnnualReturn, return_id=return_id, factory__company=company)
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
    t.setStyle(TableStyle(HEADER_STYLE + [('ALIGN', (1, 0), (1, -1), 'RIGHT')]))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={
            'title': 'Factories Act 1948 — Annual Return (Form 34)',
            'doc_number': rec.acknowledgement_no or f'FACT-AR-{rec.year}',
        })
    except Exception as e:
        logger.exception('Factory annual return PDF failed for return_id=%s: %s', return_id, e)
        raise Http404('Could not generate Factory Annual Return.')

    fname = f'Factory_AnnualReturn_{f.factory_license_no}_{rec.year}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Whitewash Register (Form 7) ───────────────────────────────────────────

@login_required
def download_whitewash_register(request, factory_id):
    from Aapp.app.factory_act import FactoryRegistration, FactoryWhitewashRegister
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    f = get_object_or_404(FactoryRegistration, factory_id=factory_id, company=company)
    records = FactoryWhitewashRegister.objects.filter(factory=f).order_by('date_done')
    if not records.exists():
        raise Http404('No whitewash records found for this factory.')

    story = [kv_table([('Establishment Name', company.company_name), ('Factory Licence No.', f.factory_license_no)])]
    story.append(Spacer(1, 6 * mm))

    rows = [['Area', 'Type of Work', 'Date Done', 'Next Due', 'Contractor']]
    for r in records:
        rows.append([r.area_description[:60], r.type_of_work, r.date_done.strftime('%d-%b-%Y'),
                     r.next_due_date.strftime('%d-%b-%Y'), r.contractor_name or '—'])
    t = Table(rows, colWidths=[150, 90, 80, 80, 90])
    t.setStyle(TableStyle(HEADER_STYLE))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={'title': 'Whitewash Register (Form 7)', 'doc_number': f.factory_license_no})
    except Exception as e:
        logger.exception('Whitewash register PDF failed for factory_id=%s: %s', factory_id, e)
        raise Http404('Could not generate Whitewash register.')

    fname = f'Whitewash_Register_{f.factory_license_no}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Vessel Examination Register (Form 8) ──────────────────────────────────

@login_required
def download_vessel_examination_register(request, factory_id):
    from Aapp.app.factory_act import FactoryRegistration, FactoryVesselExamination
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    f = get_object_or_404(FactoryRegistration, factory_id=factory_id, company=company)
    records = FactoryVesselExamination.objects.filter(factory=f).order_by('exam_date')
    if not records.exists():
        raise Http404('No vessel examination records found for this factory.')

    story = [kv_table([('Establishment Name', company.company_name), ('Factory Licence No.', f.factory_license_no)])]
    story.append(Spacer(1, 6 * mm))

    rows = [['Vessel', 'Exam Date', 'Examiner', 'Max Pressure', 'Status']]
    for r in records:
        rows.append([r.vessel_description[:60], r.exam_date.strftime('%d-%b-%Y'), r.examiner_name,
                     str(r.max_permissible_pressure), 'Fit' if r.is_fit_for_use else 'Not Fit'])
    t = Table(rows, colWidths=[150, 80, 110, 80, 70])
    t.setStyle(TableStyle(HEADER_STYLE))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={'title': 'Vessel Examination Register (Form 8)', 'doc_number': f.factory_license_no})
    except Exception as e:
        logger.exception('Vessel examination register PDF failed for factory_id=%s: %s', factory_id, e)
        raise Http404('Could not generate Vessel Examination register.')

    fname = f'Vessel_Examination_Register_{f.factory_license_no}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Accident Register (Form 26) ───────────────────────────────────────────

@login_required
def download_accident_register(request, factory_id):
    from Aapp.app.factory_act import FactoryRegistration, FactoryAccidentRegister
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    f = get_object_or_404(FactoryRegistration, factory_id=factory_id, company=company)
    records = (FactoryAccidentRegister.objects.filter(factory=f)
               .select_related('employee').order_by('accident_date'))
    if not records.exists():
        raise Http404('No accident records found for this factory.')

    story = [kv_table([('Establishment Name', company.company_name), ('Factory Licence No.', f.factory_license_no)])]
    story.append(Spacer(1, 6 * mm))

    rows = [['Employee', 'Date', 'Nature', 'Fatal?', 'Days Lost', 'DISH Ref.']]
    for r in records:
        rows.append([r.employee.name if r.employee else '—', r.accident_date.strftime('%d-%b-%Y'),
                     r.nature_of_accident, 'Yes' if r.is_fatal else 'No', str(r.days_lost),
                     r.dish_reference_no or '—'])
    t = Table(rows, colWidths=[110, 75, 130, 55, 65, 75])
    t.setStyle(TableStyle(HEADER_STYLE))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={'title': 'Accident Register (Form 26)', 'doc_number': f.factory_license_no})
    except Exception as e:
        logger.exception('Accident register PDF failed for factory_id=%s: %s', factory_id, e)
        raise Http404('Could not generate Accident register.')

    fname = f'Accident_Register_{f.factory_license_no}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ── B) Leave With Wages Register (Form 15) ───────────────────────────────────
# Company-scoped, not factory-scoped — model has no FK to FactoryRegistration.

@login_required
def download_leave_wages_register(request):
    from Aapp.app.factory_act import LeaveWithWagesRegister
    company = _company(request)
    if not company:
        raise Http404('No company selected.')
    records = (LeaveWithWagesRegister.objects.filter(employee__CompanyID=company)
               .select_related('employee').order_by('-year', 'employee__name'))
    if not records.exists():
        raise Http404('No leave-with-wages records found for this company.')

    story = [kv_table([('Establishment Name', company.company_name)])]
    story.append(Spacer(1, 6 * mm))

    rows = [['Employee', 'Year', 'Opening', 'Earned', 'Availed', 'Lapsed', 'Encashed', 'Amount (₹)']]
    for r in records:
        rows.append([r.employee.name, str(r.year), str(r.opening_balance), str(r.leave_earned),
                     str(r.leave_availed), str(r.leave_lapsed), str(r.leave_encashed), INR(r.encashment_amount)])
    t = Table(rows, colWidths=[100, 45, 60, 60, 60, 60, 65, 75])
    t.setStyle(TableStyle(HEADER_STYLE + [('ALIGN', (2, 0), (-1, -1), 'RIGHT')]))
    story.append(t)

    try:
        pdf = build_pdf(story, company, doc_meta={'title': 'Leave With Wages Register (Form 15)',
                                                    'doc_number': f'LWW-{company.company_id}'})
    except Exception as e:
        logger.exception('Leave with wages register PDF failed for company=%s: %s', company.company_id, e)
        raise Http404('Could not generate Leave With Wages register.')

    fname = f'Leave_With_Wages_Register_{company.company_name.replace(" ", "_")}.pdf'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response
