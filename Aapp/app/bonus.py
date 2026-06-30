from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from Sapp.app.company import Company
from Aapp.app.employee import employee
from Aapp.app.attandance import MONTH_CHOICES


# ── Model ─────────────────────────────────────────────────────────────────────

class bonus_record(models.Model):
    bonus_id            = models.AutoField(primary_key=True)
    company             = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    employee            = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID', related_name='bonuses')
    salary_month        = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    salary_year         = models.PositiveSmallIntegerField()

    # Bonus components
    basic_bonus         = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                            help_text='Statutory bonus as per Payment of Bonus Act (8.33% min)')
    performance_bonus   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    festival_bonus      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_bonus         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_bonus         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bonus_percentage    = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                            help_text='Percentage of basic wages (min 8.33%, max 20%)')

    # Bonus Act compliance fields
    gross_profit        = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                            help_text='Company gross profit for the accounting year (Form A)')
    allocable_surplus   = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                            help_text='67% of gross profit for non-banking companies (Form A)')

    reason              = models.CharField(max_length=500, blank=True)
    is_paid             = models.BooleanField(default=False)
    payment_date        = models.DateField(null=True, blank=True)
    created_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='bonus_created')
    created_date        = models.DateTimeField(auto_now_add=True)
    updated_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='bonus_updated')
    updated_date        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'bonus_record'
        unique_together = ('employee', 'salary_month', 'salary_year')
        ordering        = ['-salary_year', '-salary_month']

    def __str__(self):
        return f"{self.employee.employeecode} — Bonus {self.get_salary_month_display()} {self.salary_year}"

    def save(self, *args, **kwargs):
        self.total_bonus = round(
            float(self.basic_bonus) + float(self.performance_bonus) +
            float(self.festival_bonus) + float(self.other_bonus), 2
        )
        super().save(*args, **kwargs)


class bonus_set_on_set_off(models.Model):
    """Form B (Sec 15) — Register of Set-On and Set-Off of allocable surplus."""
    record_id             = models.AutoField(primary_key=True)
    company                 = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    year                      = models.PositiveSmallIntegerField()

    allocable_surplus           = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_wages_for_bonus         = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    min_bonus_amount                = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                help_text='8.33% of wages — statutory minimum')
    max_bonus_amount                  = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                help_text='20% of wages — statutory maximum')
    bonus_paid                          = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    set_on_amount                         = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                help_text='Surplus carried forward to next year')
    set_off_amount                          = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                help_text='Deficiency made up from previous years')
    cumulative_set_on                         = models.DecimalField(max_digits=15, decimal_places=2, default=0,
                                help_text='Total carried-forward set-on balance')

    created_by                                  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='bonus_set_on_created')
    created_date                                 = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'bonus_set_on_set_off'
        unique_together  = ('company', 'year')
        ordering         = ['-year']

    def __str__(self):
        return f"Bonus Set-On/Off {self.year} — {self.company.company_name}"


class bonus_annual_return(models.Model):
    """Form D (Rule 5) — Annual Return, due by 1 February of the following year."""
    return_id               = models.AutoField(primary_key=True)
    company                  = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    year                       = models.PositiveSmallIntegerField()

    total_employees              = models.PositiveIntegerField(default=0)
    total_wages                    = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    allocable_surplus                = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    bonus_percentage                   = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_bonus_paid                     = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    payment_date                           = models.DateField(null=True, blank=True,
                                help_text='Must be within 8 months of close of accounting year')

    filing_status                            = models.CharField(max_length=10, choices=[
                                ('pending', 'Pending'), ('filed', 'Filed'), ('overdue', 'Overdue'),
                             ], default='pending')
    filed_date                                = models.DateField(null=True, blank=True)
    acknowledgement_no                          = models.CharField(max_length=100, blank=True)

    created_by                                    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='bonus_returns_created')
    created_date                                   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'bonus_annual_return'
        unique_together  = ('company', 'year')
        ordering         = ['-year']

    def __str__(self):
        return f"Bonus Annual Return {self.year} — {self.company.company_name}"


# ── Helper ────────────────────────────────────────────────────────────────────

# ── ModelForms ────────────────────────────────────────────────────────────────

from django import forms as _forms

class BonusRecordForm(_forms.ModelForm):
    class Meta:
        model = bonus_record
        fields = ['salary_month', 'salary_year', 'bonus_percentage',
                  'basic_bonus', 'performance_bonus', 'festival_bonus',
                  'other_bonus', 'gross_profit', 'allocable_surplus', 'reason']

class BonusSetOnSetOffForm(_forms.ModelForm):
    class Meta:
        model = bonus_set_on_set_off
        fields = ['year', 'allocable_surplus', 'total_wages_for_bonus', 'min_bonus_amount',
                  'max_bonus_amount', 'bonus_paid', 'set_on_amount', 'set_off_amount',
                  'cumulative_set_on']

class BonusAnnualReturnForm(_forms.ModelForm):
    class Meta:
        model = bonus_annual_return
        fields = ['year', 'total_employees', 'total_wages', 'allocable_surplus',
                  'bonus_percentage', 'total_bonus_paid', 'payment_date',
                  'filing_status', 'filed_date', 'acknowledgement_no']
        widgets = {
            'payment_date': _forms.DateInput(attrs={'type': 'date'}),
            'filed_date': _forms.DateInput(attrs={'type': 'date'}),
        }


def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Bonus Record Views ───────────────────────────────────────────────────────

@login_required
def list_bonus(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    records = bonus_record.objects.filter(company=company).select_related('employee')
    rows = [{
        'cells': [r.employee.name, f'{r.salary_month}/{r.salary_year}', f'{r.bonus_percentage}%', r.total_bonus,
                  'Paid' if r.is_paid else 'Pending', r.payment_date or '—'],
        'actions': [
            {'url': reverse('update_bonus', args=[r.bonus_id]), 'label': 'Edit', 'css': 'edit'},
        ] + ([{'url': reverse('mark_bonus_paid', args=[r.bonus_id]), 'label': 'Mark Paid'}]
             if not r.is_paid else []) +
            [{'url': reverse('delete_bonus', args=[r.bonus_id]), 'label': 'Delete', 'css': 'delete'}],
    } for r in records]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Payment of Bonus Act 1965 — Bonus Register (Form A & C)',
        'columns': ['Employee', 'Year', 'Bonus %', 'Total Bonus', 'Status', 'Payment Date'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_bonus'), 'add_label': 'Add Bonus Record',
        'empty_message': 'No bonus records yet.',
    })


@login_required
def add_bonus(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    employees = employee.objects.filter(CompanyID=company, is_working=True).order_by('name')

    if request.method == 'POST':
        p = request.POST
        emp = get_object_or_404(employee, employeeid=p.get('employee_id'), CompanyID=company)
        try:
            basic_bonus = float(p.get('basic_bonus', 0) or 0)
            perf_bonus = float(p.get('performance_bonus', 0) or 0)
            fest_bonus = float(p.get('festival_bonus', 0) or 0)
            other_bonus = float(p.get('other_bonus', 0) or 0)
            rec = bonus_record.objects.create(
                company=company, employee=emp,
                salary_month=int(p.get('salary_month', 0)),
                salary_year=int(p.get('salary_year', 0)),
                bonus_percentage=p.get('bonus_percentage', 0) or 0,
                basic_bonus=basic_bonus, performance_bonus=perf_bonus,
                festival_bonus=fest_bonus, other_bonus=other_bonus,
                total_bonus=basic_bonus + perf_bonus + fest_bonus + other_bonus,
                reason=p.get('reason', ''),
                created_by=request.user,
            )
            messages.success(request, f'Bonus record created for {emp.name}.')
            return redirect('list_bonus')
        except Exception as e:
            messages.error(request, f'Error: {e}')

    return render(request, 'Aapp/generic/form.html', {
        'form': BonusRecordForm(), 'employees': employees, 'company': company,
        'page_title': 'Add Bonus Record (Form A & C)',
        'cancel_url': reverse('list_bonus'),
    })


@login_required
def update_bonus(request, bonus_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(bonus_record, bonus_id=bonus_id, company=company)

    if request.method == 'POST':
        p = request.POST
        try:
            rec.bonus_percentage = p.get('bonus_percentage', rec.bonus_percentage)
            rec.basic_bonus = float(p.get('basic_bonus', rec.basic_bonus) or 0)
            rec.performance_bonus = float(p.get('performance_bonus', rec.performance_bonus) or 0)
            rec.festival_bonus = float(p.get('festival_bonus', rec.festival_bonus) or 0)
            rec.other_bonus = float(p.get('other_bonus', rec.other_bonus) or 0)
            rec.total_bonus = rec.basic_bonus + rec.performance_bonus + rec.festival_bonus + rec.other_bonus
            rec.remarks = p.get('remarks', rec.remarks)
            rec.save()
            messages.success(request, 'Bonus record updated.')
            return redirect('list_bonus')
        except Exception as e:
            messages.error(request, f'Error: {e}')

    return render(request, 'Aapp/generic/form.html', {
        'form': BonusRecordForm(instance=rec), 'company': company,
        'page_title': f'Edit Bonus — {rec.employee.name} ({rec.salary_month}/{rec.salary_year})',
        'cancel_url': reverse('list_bonus'),
    })


@login_required
def mark_bonus_paid(request, bonus_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(bonus_record, bonus_id=bonus_id, company=company, is_paid=False)
    if request.method == 'POST':
        from datetime import date
        rec.is_paid = True
        rec.payment_date = request.POST.get('payment_date') or date.today()
        rec.save()
        messages.success(request, f'Bonus marked as paid for {rec.employee.name}.')
        return redirect('list_bonus')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Mark Bonus as Paid',
        'confirm_message': f'Mark bonus of <strong>₹{rec.total_bonus}</strong> for '
                            f'<strong>{rec.employee.name}</strong> ({rec.salary_month}/{rec.salary_year}) as paid?',
        'extra_fields': [{'name': 'payment_date', 'label': 'Payment Date', 'type': 'date'}],
        'cancel_url': reverse('list_bonus'),
    })


@login_required
def delete_bonus(request, bonus_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(bonus_record, bonus_id=bonus_id, company=company, is_paid=False)
    if request.method == 'POST':
        rec.delete()
        messages.success(request, 'Bonus record deleted.')
        return redirect('list_bonus')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Delete Bonus Record',
        'confirm_message': f'Delete bonus record for <strong>{rec.employee.name}</strong> ({rec.year})?',
        'cancel_url': reverse('list_bonus'),
    })


# ── Set-On / Set-Off Views (Form B) ──────────────────────────────────────────

@login_required
def list_set_on_set_off(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    records = bonus_set_on_set_off.objects.filter(company=company)
    rows = [{
        'cells': [r.year, r.allocable_surplus, r.bonus_paid, r.set_on_amount,
                  r.set_off_amount, r.cumulative_set_on],
        'actions': [{'url': reverse('alter_set_on_set_off', args=[r.record_id]), 'label': 'Edit', 'css': 'edit'}],
    } for r in records]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Bonus Act 1965 — Set-On / Set-Off Register (Form B)',
        'columns': ['Year', 'Allocable Surplus', 'Bonus Paid', 'Set On', 'Set Off', 'Cumulative Set-On'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_set_on_set_off'), 'add_label': 'Add Set-On/Set-Off Record',
        'empty_message': 'No Set-On/Set-Off records yet.',
    })


@login_required
def add_set_on_set_off(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    if request.method == 'POST':
        p = request.POST
        try:
            bonus_set_on_set_off.objects.create(
                company=company,
                year=int(p.get('year')),
                allocable_surplus=p.get('allocable_surplus', 0) or 0,
                total_wages_for_bonus=p.get('total_wages_for_bonus', 0) or 0,
                min_bonus_amount=p.get('min_bonus_amount', 0) or 0,
                max_bonus_amount=p.get('max_bonus_amount', 0) or 0,
                bonus_paid=p.get('bonus_paid', 0) or 0,
                set_on_amount=p.get('set_on_amount', 0) or 0,
                set_off_amount=p.get('set_off_amount', 0) or 0,
                cumulative_set_on=p.get('cumulative_set_on', 0) or 0,
                created_by=request.user,
            )
            messages.success(request, 'Set-On/Set-Off record saved.')
            return redirect('list_set_on_set_off')
        except Exception as e:
            messages.error(request, f'Error: {e}')

    return render(request, 'Aapp/generic/form.html', {
        'form': BonusSetOnSetOffForm(), 'company': company,
        'page_title': 'Add Set-On / Set-Off Record (Form B)',
        'cancel_url': reverse('list_set_on_set_off'),
    })


@login_required
def alter_set_on_set_off(request, record_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(bonus_set_on_set_off, record_id=record_id, company=company)

    if request.method == 'POST':
        p = request.POST
        rec.allocable_surplus = p.get('allocable_surplus', rec.allocable_surplus)
        rec.total_wages_for_bonus = p.get('total_wages_for_bonus', rec.total_wages_for_bonus)
        rec.min_bonus_amount = p.get('min_bonus_amount', rec.min_bonus_amount)
        rec.max_bonus_amount = p.get('max_bonus_amount', rec.max_bonus_amount)
        rec.bonus_paid = p.get('bonus_paid', rec.bonus_paid)
        rec.set_on_amount = p.get('set_on_amount', rec.set_on_amount)
        rec.set_off_amount = p.get('set_off_amount', rec.set_off_amount)
        rec.cumulative_set_on = p.get('cumulative_set_on', rec.cumulative_set_on)
        rec.save()
        messages.success(request, 'Record updated.')
        return redirect('list_set_on_set_off')

    return render(request, 'Aapp/generic/form.html', {
        'form': BonusSetOnSetOffForm(instance=rec), 'company': company,
        'page_title': f'Edit Set-On/Set-Off — {rec.year}',
        'cancel_url': reverse('list_set_on_set_off'),
    })


# ── Annual Return Views (Form D) ─────────────────────────────────────────────

@login_required
def list_bonus_returns(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    returns = bonus_annual_return.objects.filter(company=company)
    rows = [{
        'cells': [r.year, r.total_employees, r.total_wages, f'{r.bonus_percentage}%',
                  r.total_bonus_paid, r.get_filing_status_display()],
        'actions': [{'url': reverse('alter_bonus_return', args=[r.return_id]), 'label': 'Edit', 'css': 'edit'}],
    } for r in returns]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Bonus Act 1965 — Annual Return (Form D)',
        'columns': ['Year', 'Employees', 'Total Wages', 'Bonus %', 'Bonus Paid', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_bonus_return'), 'add_label': 'Add Annual Return',
        'empty_message': 'No bonus annual returns filed yet.',
    })


@login_required
def add_bonus_return(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    if request.method == 'POST':
        p = request.POST
        try:
            bonus_annual_return.objects.create(
                company=company,
                year=int(p.get('year')),
                total_employees=p.get('total_employees', 0) or 0,
                total_wages=p.get('total_wages', 0) or 0,
                allocable_surplus=p.get('allocable_surplus', 0) or 0,
                bonus_percentage=p.get('bonus_percentage', 0) or 0,
                total_bonus_paid=p.get('total_bonus_paid', 0) or 0,
                payment_date=p.get('payment_date') or None,
                filing_status=p.get('filing_status', 'pending'),
                filed_date=p.get('filed_date') or None,
                acknowledgement_no=p.get('acknowledgement_no', ''),
                created_by=request.user,
            )
            messages.success(request, 'Bonus annual return recorded.')
            return redirect('list_bonus_returns')
        except Exception as e:
            messages.error(request, f'Error: {e}')

    return render(request, 'Aapp/generic/form.html', {
        'form': BonusAnnualReturnForm(), 'company': company,
        'page_title': 'Add Bonus Annual Return (Form D)',
        'cancel_url': reverse('list_bonus_returns'),
    })


@login_required
def alter_bonus_return(request, return_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    ret = get_object_or_404(bonus_annual_return, return_id=return_id, company=company)

    if request.method == 'POST':
        p = request.POST
        ret.total_employees = p.get('total_employees', ret.total_employees)
        ret.total_wages = p.get('total_wages', ret.total_wages)
        ret.allocable_surplus = p.get('allocable_surplus', ret.allocable_surplus)
        ret.bonus_percentage = p.get('bonus_percentage', ret.bonus_percentage)
        ret.total_bonus_paid = p.get('total_bonus_paid', ret.total_bonus_paid)
        ret.payment_date = p.get('payment_date') or ret.payment_date
        ret.filing_status = p.get('filing_status', ret.filing_status)
        ret.filed_date = p.get('filed_date') or ret.filed_date
        ret.acknowledgement_no = p.get('acknowledgement_no', ret.acknowledgement_no)
        ret.save()
        messages.success(request, 'Return updated.')
        return redirect('list_bonus_returns')

    return render(request, 'Aapp/generic/form.html', {
        'form': BonusAnnualReturnForm(instance=ret), 'company': company,
        'page_title': f'Edit Bonus Annual Return — {ret.year}',
        'cancel_url': reverse('list_bonus_returns'),
    })
