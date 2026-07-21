# Aapp/app/salary_processing.py
"""
Salary Processing Module
========================
Handles monthly salary processing, payslip generation, 
bulk operations and statutory compliance (PF/ESI/PT/IT).
"""

import calendar
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime

from django.contrib import messages
from django.db import transaction
from django.db import models
from django.db.models import Sum, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from Aapp.models import (
    employee
)
from Sapp.app import company
from Capp.models import associateuser
from Capp.registry import (
    _get_company_from_session, _associate_owns_company, _log_user_activity
)

#======================================================================
#       Salary model table
#======================================================================


class salary_structure(models.Model):
    """Employee salary structure master"""
    employee_id = models.ForeignKey(employee, on_delete=models.CASCADE, db_column="EmployeeID")
    company_id = models.ForeignKey(company, on_delete=models.CASCADE, db_column="CompanyID")
    
    # Earnings (Monthly)
    basic = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hra = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    conveyance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    special_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    medical_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Fixed Deductions
    pf_employee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    esi_employee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    professional_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    income_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Employer Contributions
    pf_employer = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    esi_employer = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    effective_from = models.DateField()
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=50, null=True, blank=True)
    
    class Meta:
        db_table = 'salary_structure'

class salary_processing(models.Model):
    """Monthly salary processing batch"""
    company_id = models.ForeignKey(company, on_delete=models.CASCADE, db_column="CompanyID")
    month = models.IntegerField()  # 1-12
    year = models.IntegerField()
    
    total_employees = models.IntegerField(default=0)
    total_gross = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_net = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_employer_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, default='DRAFT')  # DRAFT, PROCESSED, APPROVED, PAID
    
    processed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=50, null=True, blank=True)
    
    class Meta:
        db_table = 'salary_processing'
        unique_together = ['company_id', 'month', 'year']

class salary_slip(models.Model):
    """Individual employee salary slip"""
    processing_id = models.ForeignKey(salary_processing, on_delete=models.CASCADE, db_column="ProcessingID")
    employee_id = models.ForeignKey(employee, on_delete=models.CASCADE, db_column="EmployeeID")
    company_id = models.ForeignKey(company, on_delete=models.CASCADE, db_column="CompanyID")
    salary_structure_id = models.ForeignKey(salary_structure, on_delete=models.SET_NULL, null=True, db_column="StructureID")
    
    # Attendance
    total_days = models.IntegerField(default=0)
    working_days = models.IntegerField(default=0)
    present_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    paid_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    leave_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    absent_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    overtime_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Earnings (Calculated)
    basic_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hra_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    conveyance_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    special_allowance_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    medical_allowance_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_allowance_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    overtime_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gross_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Deductions (Calculated)
    pf_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    esi_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    professional_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    income_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    loan_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    advance_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    late_fine = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    net_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Employer Cost
    pf_employer_contribution = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    esi_employer_contribution = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    employer_total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=50, null=True, blank=True)
    
    class Meta:
        db_table = 'salary_slip'
        unique_together = ['processing_id', 'employee_id']

# =====================================================================
# CONSTANTS - Statutory Rates (Configurable per Company)
# =====================================================================

PF_EMPLOYEE_RATE = Decimal('0.12')       # 12% of basic
PF_EMPLOYER_RATE = Decimal('0.13')       # 13% (12% EPF + 1% EPS)
PF_WAGE_CEILING = Decimal('15000')       # Max basic for PF calculation
ESI_EMPLOYEE_RATE = Decimal('0.0075')    # 0.75%
ESI_EMPLOYER_RATE = Decimal('0.0325')    # 3.25%
ESI_WAGE_CEILING = Decimal('21000')       # Max gross for ESI
PT_STATES = {                            # Professional Tax slabs (example)
    'Maharashtra': [(10000, 200), (Decimal('inf'), 200)],  # Up to 10000: 175, above: 200
    'Karnataka': [(15000, 200), (Decimal('inf'), 200)],
}
STANDARD_WORKING_DAYS = Decimal('26')    # Default working days/month
STANDARD_WORKING_HOURS = Decimal('8')    # Hours per day


# =====================================================================
# UTILITY FUNCTIONS
# =====================================================================

def _decimal_round(value):
    """Round to 2 decimal places using banker's rounding."""
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _get_selected_company(request):
    """Get company from session with ownership validation."""
    company = _get_company_from_session(request)
    if company and _associate_owns_company(request.user, company):
        return company
    return None


def _get_days_in_month(month, year):
    """Return total days in given month."""
    return calendar.monthrange(year, month)[1]


def _get_working_days(month, year):
    """
    Calculate approximate working days excluding Sundays.
    (For exact calculation, integrate with attendance module.)
    """
    cal = calendar.Calendar()
    working = 0
    for week in cal.monthdayscalendar(year, month):
        # week[6] is Sunday
        working += sum(1 for d in week[:6] if d != 0)
    return working


def _get_attendance_summary(employee_obj, month, year):
    """
    Pull attendance data. Falls back to full attendance
    if attendance records unavailable.
    """
    try:
        from Aapp.models import attandance  # Local import to avoid circular
        records = attandance.objects.filter(
            employeeid=employee_obj,
            date__year=year,
            date__month=month,
        )
        present = records.filter(status='P').count()
        absent = records.filter(status='A').count()
        leave = records.filter(status='L').count()
        overtime = records.aggregate(
            total=Sum('overtime_hours'))['total'] or Decimal('0')
        return {
            'present_days': Decimal(present),
            'absent_days': Decimal(absent),
            'leave_days': Decimal(leave),
            'overtime_hours': Decimal(str(overtime)),
        }
    except Exception:
        # Default to full attendance
        working = _get_working_days(month, year)
        return {
            'present_days': Decimal(working),
            'absent_days': Decimal('0'),
            'leave_days': Decimal('0'),
            'overtime_hours': Decimal('0'),
        }


def _calculate_pf(basic, pf_applicable=True):
    """Calculate PF based on wage ceiling."""
    if not pf_applicable:
        return Decimal('0'), Decimal('0')
    pf_base = min(basic, PF_WAGE_CEILING)
    employee_pf = pf_base * PF_EMPLOYEE_RATE
    employer_pf = pf_base * PF_EMPLOYER_RATE
    return _decimal_round(employee_pf), _decimal_round(employer_pf)


def _calculate_esi(gross, esi_applicable=True):
    """Calculate ESI based on wage ceiling."""
    if not esi_applicable or gross > ESI_WAGE_CEILING:
        return Decimal('0'), Decimal('0')
    employee_esi = gross * ESI_EMPLOYEE_RATE
    employer_esi = gross * ESI_EMPLOYER_RATE
    return _decimal_round(employee_esi), _decimal_round(employer_esi)


def _calculate_pt(gross, state_name):
    """Professional Tax based on state slab."""
    slabs = PT_STATES.get(state_name, [])
    for limit, tax in slabs:
        if gross <= limit:
            return Decimal(tax)
    return Decimal('0')


def _calculate_overtime(per_hour_basic, overtime_hours):
    """Overtime = 2x hourly rate."""
    if overtime_hours <= 0:
        return Decimal('0')
    overtime_rate = (per_hour_basic / STANDARD_WORKING_HOURS) * Decimal('2')
    return _decimal_round(overtime_rate * overtime_hours)


# =====================================================================
# SALARY CALCULATION ENGINE
# =====================================================================

def calculate_employee_salary(employee_obj, structure, month, year):
    """
    Calculate complete salary for one employee for given month.
    
    Returns dict with all earnings, deductions and net pay.
    """
    total_days = Decimal(_get_days_in_month(month, year))
    working_days = Decimal(_get_working_days(month, year))
    
    # Attendance data
    attendance = _get_attendance_summary(employee_obj, month, year)
    paid_days = attendance['present_days'] + attendance['leave_days']
    
    # Proration factor
    proration = paid_days / working_days if working_days > 0 else Decimal('0')
    
    # Base salary from structure
    basic = Decimal(str(structure.basic))
    hra = Decimal(str(structure.hra))
    conveyance = Decimal(str(structure.conveyance))
    special = Decimal(str(structure.special_allowance))
    medical = Decimal(str(structure.medical_allowance))
    other = Decimal(str(structure.other_allowance))
    
    # Pro-rated earnings
    basic_earned = _decimal_round(basic * proration)
    hra_earned = _decimal_round(hra * proration)
    conv_earned = _decimal_round(conveyance * proration)
    special_earned = _decimal_round(special * proration)
    medical_earned = _decimal_round(medical * proration)
    other_earned = _decimal_round(other * proration)
    
    # Overtime calculation
    hourly_basic = basic / Decimal('30') / STANDARD_WORKING_HOURS
    overtime_amt = _calculate_overtime(hourly_basic, attendance['overtime_hours'])
    
    gross = (basic_earned + hra_earned + conv_earned + 
             special_earned + medical_earned + other_earned + overtime_amt)
    
    # Bonus (from bonus module if available)
    bonus_amt = Decimal('0')
    try:
        from Aapp.models import bonus
        bonus_rec = bonus.objects.filter(
            employeeid=employee_obj, month=month, year=year
        ).first()
        if bonus_rec:
            bonus_amt = Decimal(str(bonus_rec.amount))
            gross += bonus_amt
    except Exception:
        pass
    
    # Statutory deductions
    pf_applicable = getattr(employee_obj, 'pf_applicable', True)
    esi_applicable = getattr(employee_obj, 'esi_applicable', True)
    
    pf_emp, pf_empr = _calculate_pf(basic, pf_applicable)
    esi_emp, esi_empr = _calculate_esi(gross, esi_applicable)
    
    # Professional Tax (from employee state)
    state_name = ''
    try:
        if employee_obj.state_id:
            state_name = employee_obj.state_id.state_name
    except Exception:
        pass
    pt = _calculate_pt(gross, state_name)
    
    # Fixed deductions (pro-rated)
    fixed_pt = Decimal(str(structure.professional_tax))
    fixed_it = Decimal(str(structure.income_tax)) * proration
    
    total_deductions = pf_emp + esi_emp + pt + fixed_pt + fixed_it
    
    net_pay = gross - total_deductions
    employer_cost = gross + pf_empr + esi_empr
    
    return {
        'total_days': int(total_days),
        'working_days': int(working_days),
        'present_days': attendance['present_days'],
        'paid_days': paid_days,
        'leave_days': attendance['leave_days'],
        'absent_days': attendance['absent_days'],
        'overtime_hours': attendance['overtime_hours'],
        
        'basic_earned': basic_earned,
        'hra_earned': hra_earned,
        'conveyance_earned': conv_earned,
        'special_allowance_earned': special_earned,
        'medical_allowance_earned': medical_earned,
        'other_allowance_earned': other_earned,
        'overtime_amount': overtime_amt,
        'bonus_amount': bonus_amt,
        'gross_earnings': _decimal_round(gross),
        
        'pf_deduction': pf_emp,
        'esi_deduction': esi_emp,
        'professional_tax': pt,
        'income_tax': _decimal_round(fixed_it),
        'total_deductions': _decimal_round(total_deductions),
        
        'net_pay': _decimal_round(net_pay),
        
        'pf_employer_contribution': pf_empr,
        'esi_employer_contribution': esi_empr,
        'employer_total_cost': _decimal_round(employer_cost),
    }


# =====================================================================
# VIEWS - Salary Processing Workflow
# =====================================================================

def salary_dashboard(request):
    """Main salary processing dashboard."""
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')
    
    current_month = timezone.now().month
    current_year = timezone.now().year
    
    # Recent processing records
    recent_batches = salary_processing.objects.filter(
        company_id=company
    ).order_by('-year', '-month')[:6]
    
    # Pending salaries count
    employees_count = employee.objects.filter(
        CompanyID=company, status='Active'
    ).count()
    
    structures_count = salary_structure.objects.filter(
        company_id=company, is_active=True
    ).count()
    
    context = {
        'company': company,
        'recent_batches': recent_batches,
        'employees_count': employees_count,
        'structures_count': structures_count,
        'current_month': current_month,
        'current_year': current_year,
        'month_name': calendar.month_name[current_month],
    }
    return render(request, 'salary/dashboard.html', context)


def create_salary_batch(request):
    """Initiate salary processing for a month."""
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')

def create_salary_batch(request):
    """Initiate salary processing for a month."""
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                month = int(request.POST.get('month'))
                year = int(request.POST.get('year'))
                
                # Validate month/year
                if month < 1 or month > 12:
                    raise ValueError('Invalid month')
                if year < 2000 or year > 2100:
                    raise ValueError('Invalid year')
                
                # Check if already processed
                existing = salary_processing.objects.filter(
                    company_id=company, month=month, year=year
                ).first()
                if existing:
                    if existing.status == 'APPROVED':
                        messages.warning(
                            request, 
                            f'Salary for {calendar.month_name[month]} {year} is already approved.'
                        )
                        return redirect('salary_dashboard')
                    elif existing.status == 'PROCESSED':
                        messages.info(
                            request, 
                            'Salary batch already processed. Use view/edit option.'
                        )
                        return redirect('view_salary_batch', batch_id=existing.id)
                
                # Create batch record
                batch = salary_processing.objects.create(
                    company_id=company,
                    month=month,
                    year=year,
                    status='DRAFT',
                    created_by=request.user.username,
                )
                
                _log_user_activity(
                    request.user, 
                    f'Created salary batch for {calendar.month_name[month]} {year}'
                )
                
                messages.success(
                    request, 
                    f'Salary batch created for {calendar.month_name[month]} {year}. '
                    'Proceed to process employees.'
                )
                return redirect('process_salary_batch', batch_id=batch.id)
                
        except Exception as e:
            messages.error(request, f'Error creating batch: {str(e)}')
            return redirect('create_salary_batch')
    
    # GET - Show form
    today = timezone.now()
    context = {
        'company': company,
        'current_month': today.month,
        'current_year': today.year,
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'years': range(today.year - 2, today.year + 1),
    }
    return render(request, 'salary/create_batch.html', context)


def process_salary_batch(request, batch_id):
    """
    Process salary for all active employees in the batch.
    Calculates and saves individual salary slips.
    """
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')
    
    batch = salary_processing.objects.filter(
        id=batch_id, company_id=company
    ).first()
    if not batch:
        messages.error(request, 'Salary batch not found.')
        return redirect('salary_dashboard')
    
    if batch.status == 'APPROVED':
        messages.warning(request, 'Cannot modify approved batch.')
        return redirect('view_salary_batch', batch_id=batch.id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Delete any existing slips (for re-processing)
                salary_slip.objects.filter(processing_id=batch).delete()
                
                # Get all active employees with salary structures
                employees = employee.objects.filter(
                    CompanyID=company, status='Active'
                ).select_related('state_id')
                
                processed = 0
                skipped = 0
                error_rows = []
                total_gross = Decimal('0')
                total_deductions = Decimal('0')
                total_net = Decimal('0')
                total_employer = Decimal('0')
                
                for emp in employees:
                    structure = salary_structure.objects.filter(
                        employee_id=emp, company_id=company, is_active=True
                    ).first()
                    
                    if not structure:
                        skipped += 1
                        error_rows.append(
                            f'{emp.employeecode} - {emp.name}: No salary structure'
                        )
                        continue
                    
                    try:
                        calc = calculate_employee_salary(
                            emp, structure, batch.month, batch.year
                        )
                        
                        salary_slip.objects.create(
                            processing_id=batch,
                            employee_id=emp,
                            company_id=company,
                            salary_structure_id=structure,
                            **calc,
                            created_by=request.user.username,
                        )
                        
                        total_gross += calc['gross_earnings']
                        total_deductions += calc['total_deductions']
                        total_net += calc['net_pay']
                        total_employer += calc['employer_total_cost']
                        processed += 1
                        
                    except Exception as e:
                        skipped += 1
                        error_rows.append(
                            f'{emp.employeecode} - {emp.name}: {str(e)}'
                        )
                
                # Update batch totals
                batch.total_employees = processed
                batch.total_gross = _decimal_round(total_gross)
                batch.total_deductions = _decimal_round(total_deductions)
                batch.total_net = _decimal_round(total_net)
                batch.total_employer_cost = _decimal_round(total_employer)
                batch.status = 'PROCESSED'
                batch.processed_at = timezone.now()
                batch.updated_by = request.user.username
                batch.save()
                
                _log_user_activity(
                    request.user,
                    f'Processed {processed} salaries for {calendar.month_name[batch.month]} {batch.year}'
                )
                
                if error_rows:
                    request.session['salary_errors'] = error_rows
                
                messages.success(
                    request, 
                    f'Salary processed: {processed} employees. '
                    f'Skipped: {skipped}.'
                )
                return redirect('view_salary_batch', batch_id=batch.id)
                
        except Exception as e:
            messages.error(request, f'Error processing: {str(e)}')
            return redirect('process_salary_batch', batch_id=batch_id)
    
    # GET - Show employees to process
    slips = salary_slip.objects.filter(processing_id=batch)
    context = {
        'company': company,
        'batch': batch,
        'month_name': calendar.month_name[batch.month],
        'slips': slips,
        'employees_count': employee.objects.filter(
            CompanyID=company, status='Active'
        ).count(),
    }
    return render(request, 'salary/process_batch.html', context)


def view_salary_batch(request, batch_id):
    """View all salary slips in a batch."""
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')
    
    batch = salary_processing.objects.filter(
        id=batch_id, company_id=company
    ).first()
    if not batch:
        messages.error(request, 'Salary batch not found.')
        return redirect('salary_dashboard')
    
    slips = salary_slip.objects.filter(
        processing_id=batch
    ).select_related('employee_id').order_by('employee_id__employeecode')
    
    errors = request.session.pop('salary_errors', [])
    
    context = {
        'company': company,
        'batch': batch,
        'month_name': calendar.month_name[batch.month],
        'slips': slips,
        'errors': errors,
    }
    return render(request, 'salary/view_batch.html', context)


def view_salary_slip(request, slip_id):
    """View individual employee salary slip with full breakdown."""
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')
    
    slip = salary_slip.objects.filter(
        id=slip_id, company_id=company
    ).select_related(
        'employee_id', 'employee_id__state_id', 
        'employee_id__district_id', 'salary_structure_id'
    ).first()
    
    if not slip:
        messages.error(request, 'Salary slip not found.')
        return redirect('salary_dashboard')
    
    batch = slip.processing_id
    
    context = {
        'company': company,
        'slip': slip,
        'batch': batch,
        'month_name': calendar.month_name[batch.month],
    }
    return render(request, 'salary/view_slip.html', context)


def edit_salary_slip(request, slip_id):
    """Edit individual salary slip (e.g., manual adjustments)."""
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')
    
    slip = salary_slip.objects.filter(
        id=slip_id, company_id=company
    ).first()
    if not slip:
        messages.error(request, 'Salary slip not found.')
        return redirect('salary_dashboard')
    
    if slip.processing_id.status == 'APPROVED':
        messages.warning(request, 'Cannot edit approved slip.')
        return redirect('view_salary_slip', slip_id=slip.id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Manual adjustments
                slip.loan_deduction = Decimal(request.POST.get('loan_deduction', 0))
                slip.advance_deduction = Decimal(request.POST.get('advance_deduction', 0))
                slip.late_fine = Decimal(request.POST.get('late_fine', 0))
                slip.other_deduction = Decimal(request.POST.get('other_deduction', 0))
                slip.other_allowance_earned = Decimal(
                    request.POST.get('other_allowance_earned', 0)
                )
                slip.bonus_amount = Decimal(request.POST.get('bonus_amount', 0))
                
                # Recalculate totals
                gross = (
                    slip.basic_earned + slip.hra_earned + 
                    slip.conveyance_earned + slip.special_allowance_earned +
                    slip.medical_allowance_earned + slip.other_allowance_earned +
                    slip.overtime_amount + slip.bonus_amount
                )
                deductions = (
                    slip.pf_deduction + slip.esi_deduction +
                    slip.professional_tax + slip.income_tax +
                    slip.loan_deduction + slip.advance_deduction +
                    slip.late_fine + slip.other_deduction
                )
                
                slip.gross_earnings = _decimal_round(gross)
                slip.total_deductions = _decimal_round(deductions)
                slip.net_pay = _decimal_round(gross - deductions)
                slip.employer_total_cost = _decimal_round(
                    gross + slip.pf_employer_contribution + slip.esi_employer_contribution
                )
                slip.updated_by = request.user.username
                slip.save()
                
                # Update batch totals
                batch = slip.processing_id
                totals = salary_slip.objects.filter(processing_id=batch).aggregate(
                    total_gross=Sum('gross_earnings'),
                    total_deductions=Sum('total_deductions'),
                    total_net=Sum('net_pay'),
                    total_employer=Sum('employer_total_cost'),
                )
                batch.total_gross = totals['total_gross'] or Decimal('0')
                batch.total_deductions = totals['total_deductions'] or Decimal('0')
                batch.total_net = totals['total_net'] or Decimal('0')
                batch.total_employer_cost = totals['total_employer'] or Decimal('0')
                batch.save()
                
                messages.success(request, 'Salary slip updated successfully.')
                return redirect('view_salary_slip', slip_id=slip.id)
                
        except Exception as e:
            messages.error(request, f'Error updating: {str(e)}')
    
    context = {
        'company': company,
        'slip': slip,
        'batch': slip.processing_id,
        'month_name': calendar.month_name[slip.processing_id.month],
    }
    return render(request, 'salary/edit_slip.html', context)


def approve_salary_batch(request, batch_id):
    """Mark salary batch as approved (locks editing)."""
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')
    
    batch = salary_processing.objects.filter(
        id=batch_id, company_id=company
    ).first()
    if not batch:
        messages.error(request, 'Salary batch not found.')
        return redirect('salary_dashboard')
    
    if batch.status != 'PROCESSED':
        messages.warning(request, 'Only processed batches can be approved.')
        return redirect('view_salary_batch', batch_id=batch.id)
    
    try:
        batch.status = 'APPROVED'
        batch.approved_at = timezone.now()
        batch.updated_by = request.user.username
        batch.save()
        
        _log_user_activity(
            request.user,
            f'Approved salary batch {calendar.month_name[batch.month]} {batch.year}'
        )
        
        messages.success(request, 'Salary batch approved successfully.')
    except Exception as e:
        messages.error(request, f'Error approving: {str(e)}')
    
    return redirect('view_salary_batch', batch_id=batch.id)


def delete_salary_batch(request, batch_id):
    """Delete a draft or processed batch."""
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')
    
    batch = salary_processing.objects.filter(
        id=batch_id, company_id=company
    ).first()
    if not batch:
        messages.error(request, 'Salary batch not found.')
        return redirect('salary_dashboard')
    
    if batch.status == 'APPROVED':
        messages.warning(request, 'Cannot delete approved batch.')
        return redirect('view_salary_batch', batch_id=batch.id)
    
    if request.method == 'POST':
        try:
            month_year = f'{calendar.month_name[batch.month]} {batch.year}'
            batch.delete()
            messages.success(request, f'Salary batch {month_year} deleted.')
            return redirect('salary_dashboard')
        except Exception as e:
            messages.error(request, f'Error deleting: {str(e)}')
    
    context = {
        'company': company,
        'batch': batch,
        'month_name': calendar.month_name[batch.month],
    }
    return render(request, 'salary/delete_batch.html', context)


# =====================================================================
# SALARY STRUCTURE MANAGEMENT
# =====================================================================

def list_salary_structures(request):
    """List all employee salary structures."""
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')
    
    structures = salary_structure.objects.filter(
        company_id=company, is_active=True
    ).select_related('employee_id').order_by('employee_id__employeecode')
    
    context = {
        'company': company,
        'structures': structures,
    }
    return render(request, 'salary/structure_list.html', context)


def create_salary_structure(request):
    """Create salary structure for an employee."""
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                emp_id = request.POST.get('employee_id')
                emp = employee.objects.filter(
                    id=emp_id, CompanyID=company, status='Active'
                ).first()
                if not emp:
                    raise ValueError('Employee not found')
                
                # Deactivate old structures
                salary_structure.objects.filter(
                    employee_id=emp, company_id=company
                ).update(is_active=False)
                
                structure = salary_structure.objects.create(
                    employee_id=emp,
                    company_id=company,
                    basic=Decimal(request.POST.get('basic', 0)),
                    hra=Decimal(request.POST.get('hra', 0)),
                    conveyance=Decimal(request.POST.get('conveyance', 0)),
                    special_allowance=Decimal(request.POST.get('special_allowance', 0)),
                    medical_allowance=Decimal(request.POST.get('medical_allowance', 0)),
                    other_allowance=Decimal(request.POST.get('other_allowance', 0)),
                    pf_employee=Decimal(request.POST.get('pf_employee', 0)),
                    esi_employee=Decimal(request.POST.get('esi_employee', 0)),
                    professional_tax=Decimal(request.POST.get('professional_tax', 0)),
                    income_tax=Decimal(request.POST.get('income_tax', 0)),
                    pf_employer=Decimal(request.POST.get('pf_employer', 0)),
                    esi_employer=Decimal(request.POST.get('esi_employer', 0)),
                    effective_from=request.POST.get('effective_from'),
                    is_active=True,
                    created_by=request.user.username,
                )
                
                messages.success(
                    request, 
                    f'Salary structure created for {emp.name}.'
                )
                return redirect('view_salary_structure', structure_id=structure.id)
                
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    employees = employee.objects.filter(
        CompanyID=company, status='Active'
    ).order_by('employeecode')
    
    context = {
        'company with_structure': salary_structure.objects.filter(
            company_id=company, is_active=True
        ).values_list('employee_id_id', flat=True),
        'company': company,
        'employees': employees,
    }
    return render(request, 'salary/structure_create.html', context)


def view_salary_structure(request, structure_id):
    """View individual salary structure."""
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')
    
    structure = salary_structure.objects.filter(
        id=structure_id, company_id=company
    ).select_related('employee_id').first()
    
    if not structure:
        messages.error(request, 'Salary structure not found.')
        return redirect('list_salary_structures')
    
    # Calculate monthly gross
    monthly_gross = (
        structure.basic + structure.hra + structure.conveyance +
        structure.special_allowance + structure.medical_allowance +
        structure.other_allowance
    )
    yearly_gross = monthly_gross * 12
    
    context = {
        'company': company,
        'structure': structure,
        'monthly_gross': _decimal_round(monthly_gross),
        'yearly_gross': _decimal_round(yearly_gross),
    }
    return render(request, 'salary/structure_view.html', context)


# =====================================================================
# EXCEL EXPORT/IMPORT
# =====================================================================

def export_salary_register(request, batch_id):
    """Export complete salary register to Excel."""
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')
    
    batch = salary_processing.objects.filter(
        id=batch_id, company_id=company
    ).first()
    if not batch:
        messages.error(request, 'Salary batch not found.')
        return redirect('salary_dashboard')
    
    slips = salary_slip.objects.filter(
        processing_id=batch
    ).select_related('employee_id').order_by('employee_id__employeecode')
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f'Salary_{calendar.month_name[batch.month]}_{batch.year}'
    
    # Header styling
    hdr_fill = PatternFill('solid', fgColor='1D3557')
    hdr_font = Font(color='FFFFFF', bold=True, size=11)
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    
    # Title
    ws.merge_cells('A1:T1')
    ws['A1'] = (
        f'{company.company_name} - Salary Register - '
        f'{calendar.month_name[batch.month]} {batch.year}'
    )
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center')
    
    # Headers
    headers = [
        'Emp Code', 'Name', 'Working Days', 'Paid Days',
        'Basic', 'HRA', 'Conveyance', 'Special', 'Medical', 'Other',
        'Overtime', 'Bonus', 'Gross',
        'PF', 'ESI', 'PT', 'IT', 'Total Ded', 'Net Pay'
    ]
    
    header_row = 3
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col, value=h)
        cell.fill = hdr_fill
        cell.font = hdr_font
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        cell.border = border
        ws.column_dimensions[cell.column_letter].width = 13
    
    # Data rows
    for row_num, slip in enumerate(slips, start=header_row + 1):
        data = [
            slip.employee_id.employeecode,
            slip.employee_id.name,
            slip.working_days,
            float(slip.paid_days),
            float(slip.basic_earned),
            float(slip.hra_earned),
            float(slip.conveyance_earned),
            float(slip.special_allowance_earned),
            float(slip.medical_allowance_earned),
            float(slip.other_allowance_earned),
            float(slip.overtime_amount),
            float(slip.bonus_amount),
            float(slip.gross_earnings),
            float(slip.pf_deduction),
            float(slip.esi_deduction),
            float(slip.professional_tax),
            float(slip.income_tax),
            float(slip.total_deductions),
            float(slip.net_pay),
        ]
        for col, value in enumerate(data, 1):
            cell = ws.cell(row=row_num, column=col, value=value)
            cell.border = border
            if col >= 4:
                cell.alignment = Alignment(horizontal='right')
                cell.number_format = '#,##0.00'
    
    # Totals row
    total_row = header_row + len(slips) + 1
    ws.cell(row=total_row, column=1, value='TOTAL').font = Font(bold=True)
    for col in range(4, 20):
        col_letter = openpyxl.utils.get_column_letter(col)
        ws.cell(
            row=total_row, 
            column=col, 
            value=f'=SUM({col_letter}{header_row + 1}:{col_letter}{total_row - 1})'
        ).font = Font(bold=True)
        ws.cell(row=total_row, column=col).number_format = '#,##0.00'
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = (
        f'Salary_{company.company_name.replace(" ", "_")}_'
        f'{batch.month}_{batch.year}.xlsx'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


def export_bank_advice(request, batch_id):
    """Export bank transfer advice file."""
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')
    
    batch = salary_processing.objects.filter(
        id=batch_id, company_id=company
    ).first()
    if not batch:
        messages.error(request, 'Salary batch not found.')
        return redirect('salary_dashboard')
    
    slips = salary_slip.objects.filter(
        processing_id=batch, net_pay__gt=0
    ).select_related('employee_id').order_by('employee_id__employeecode')
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Bank_Advice'
    
    headers = [
        'Emp Code', 'Employee Name', 'Bank Name', 
        'Account Number', 'IFSC Code', 'Net Pay', 'Remarks'
    ]
    
    hdr_fill = PatternFill('solid', fgColor='2D6A4F')
    hdr_font = Font(color='FFFFFF', bold=True)
    
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = hdr_fill
        cell.font = hdr_font
        cell.alignment = Alignment(horizontal='center')
        ws.column_dimensions[cell.column_letter].width = 18
    
    total = Decimal('0')
    for row_num, slip in enumerate(slips, start=2):
        emp = slip.employee_id
        ws.cell(row=row_num, column=1, value=emp.employeecode)
        ws.cell(row=row_num, column=2, value=emp.name)
        ws.cell(row=row_num, column=3, value=getattr(emp, 'bank_name', ''))
        ws.cell(row=row_num, column=4, value=getattr(emp, 'bank_account_no', ''))
        ws.cell(row=row_num, column=5, value=getattr(emp, 'ifsc_code', ''))
        ws.cell(row=row_num, column=6, value=float(slip.net_pay)).number_format = '#,##0.00'
        total += slip.net_pay
    
    # Total row
    total_row = len(slips) + 2
    ws.cell(row=total_row, column=5, value='TOTAL:').font = Font(bold=True)
    ws.cell(row=total_row, column=6, value=float(total)).font = Font(bold=True)
    ws.cell(row=total_row, column=6).number_format = '#,##0.00'
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = (
        f'attachment; filename="BankAdvice_{batch.month}_{batch.year}.xlsx"'
    )
    wb.save(response)
    return response


def download_salary_template(request):
    """Download Excel template for bulk salary structure upload."""
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Salary_Structure'
    
    headers = [
        'employeecode*', 'basic*', 'hra', 'conveyance', 
        'special_allowance', 'medical_allowance', 'other_allowance',
        'pf_employee', 'esi_employee', 'professional_tax', 'income_tax',
        'effective_from*'
    ]
    
    hdr_fill = PatternFill('solid', fgColor='1D3557')
    hdr_font = Font(color='FFFFFF', bold=True)
    
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = hdr_fill
        cell.font = hdr_font
        ws.column_dimensions[cell.column_letter].width = 18
    
    # Add notes
    ws.cell(row=3, column=1, value='* Required fields').font = Font(italic=True, color='red')
    ws.cell(row=4, column=1, value='Date format: YYYY-MM-DD').font = Font(italic=True)
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="Salary_Structure_Template.xlsx"'
    wb.save(response)
    return response


def import_salary_structures(request):
    """Bulk import salary structures from Excel."""
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')
    
    if request.method != 'POST':
        return redirect('list_salary_structures')
    
    if 'excel_file' not in request.FILES:
        messages.error(request, 'No file uploaded.')
        return redirect('list_salary_structures')
    
    excel_file = request.FILES['excel_file']
    
    if not excel_file.name.endswith(('.xlsx', '.xls')):
        messages.error(request, 'Please upload a valid Excel file.')
        return redirect('list_salary_structures')
    
    try:
        wb = openpyxl.load_workbook(excel_file)
        ws = wb.active
        
        # Build employee lookup map
        employees_map = {
            e.employeecode: e 
            for e in employee.objects.filter(CompanyID=company)
        }
        
        created = 0
        errors = 0
        error_rows = []
        
        for row_num, row in enumerate(
            ws.iter_rows(min_row=2, values_only=True), start=2
        ):
            if not any(row):
                continue
            
            try:
                emp_code = str(row[0]).strip() if row[0] else ''
                if not emp_code:
                    error_rows.append(f'Row {row_num}: Employee code is required.')
                    errors += 1
                    continue
                
                emp = employees_map.get(emp_code)
                if not emp:
                    error_rows.append(
                        f'Row {row_num}: Employee code "{emp_code}" not found.'
                    )
                    errors += 1
                    continue
                
                basic = Decimal(str(row[1] or 0))
                effective_from_str = row[11]
                
                if not effective_from_str:
                    error_rows.append(f'Row {row_num}: Effective from date required.')
                    errors += 1
                    continue
                
                # Parse date
                if isinstance(effective_from_str, datetime):
                    effective_from = effective_from_str.date()
                else:
                    effective_from = datetime.strptime(
                        str(effective_from_str), '%Y-%m-%d'
                    ).date()
                
                # Deactivate old structures
                salary_structure.objects.filter(
                    employee_id=emp, company_id=company
                ).update(is_active=False)
                
                salary_structure.objects.create(
                    employee_id=emp,
                    company_id=company,
                    basic=basic,
                    hra=Decimal(str(row[2] or 0)),
                    conveyance=Decimal(str(row[3] or 0)),
                    special_allowance=Decimal(str(row[4] or 0)),
                    medical_allowance=Decimal(str(row[5] or 0)),
                    other_allowance=Decimal(str(row[6] or 0)),
                    pf_employee=Decimal(str(row[7] or 0)),
                    esi_employee=Decimal(str(row[8] or 0)),
                    professional_tax=Decimal(str(row[9] or 0)),
                    income_tax=Decimal(str(row[10] or 0)),
                    effective_from=effective_from,
                    is_active=True,
                    created_by=request.user.username,
                )
                created += 1
                
            except Exception as e:
                error_rows.append(f'Row {row_num}: {str(e)}')
                errors += 1
        
        if error_rows:
            request.session['import_errors'] = error_rows[:50]
        
        messages.success(
            request, 
            f'Import complete: {created} created, {errors} errors.'
        )
        
    except Exception as e:
        messages.error(request, f'Error reading file: {str(e)}')
    
    return redirect('list_salary_structures')


# =====================================================================
# STATUTORY REPORTS
# =====================================================================

def pf_report(request):
    """Generate PF calculation report for the month."""
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')
    
    month = int(request.GET.get('month', timezone.now().month))
    year = int(request.GET.get('year', timezone.now().year))
    
    batch = salary_processing.objects.filter(
        company_id=company, month=month, year=year
    ).first()
    
    slips = []
    totals = {
        'pf_employee': Decimal('0'), 'pf_employer': Decimal('0'),
        'gross': Decimal('0'),
    }
    
    if batch:
        slips_data = salary_slip.objects.filter(
            processing_id=batch
        ).select_related('employee_id').order_by('employee_id__employeecode')
        
        for s in slips_data:
            if s.pf_deduction > 0 or s.pf_employer_contribution > 0:
                slips.append(s)
                totals['pf_employee'] += s.pf_deduction
                totals['pf_employer'] += s.pf_employer_contribution
                totals['gross'] += s.gross_earnings
    
    context = {
        'company': company,
        'slips': slips,
        'totals': {k: _decimal_round(v) for k, v in totals.items()},
        'month': month,
        'year': year,
        'month_name': calendar.month_name[month],
        'pf_employee_rate': PF_EMPLOYEE_RATE * 100,
        'pf_employer_rate': PF_EMPLOYER_RATE * 100,
    }
    return render(request, 'salary/pf_report.html', context)


def esi_report(request):
    """Generate ESI calculation report for the month."""
    company = _get_selected_company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('associate_dashboard')
    
    month = int(request.GET.get('month', timezone.now().month))
    year = int(request.GET.get('year', timezone.now().year))
    
    batch = salary_processing.objects.filter(
        company_id=company, month=month, year=year
    ).first()
    
    slips = []
    totals = {
        'esi_employee': Decimal('0'), 'esi_employer': Decimal('0'),
        'gross': Decimal('0'),
    }
    
    if batch:
        slips_data = salary_slip.objects.filter(
            processing_id=batch, esi_deduction__gt=0
        ).select_related('employee_id').order_by('employee_id__employeecode')
        
        for s in slips_data:
            slips.append(s)
            totals['esi_employee'] += s.esi_deduction
            totals['esi_employer'] += s.esi_employer_contribution
            totals['gross'] += s.gross_earnings
    
    context = {
        'company': company,
        'slips': slips,
        'totals': {k: _decimal_round(v) for k, v in totals.items()},
        'month': month,
        'year': year,
        'month_name': calendar.month_name[month],
        'esi_employee_rate': ESI_EMPLOYEE_RATE * 100,
        'esi_employer_rate': ESI_EMPLOYER_RATE * 100,
    }
    return render(request, 'salary/esi_report.html', context)