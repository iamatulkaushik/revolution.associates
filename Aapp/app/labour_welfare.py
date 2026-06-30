"""
Punjab Labour Welfare Fund Act, 1965 (applicable to Haryana).

Employer contributes twice a year (June & December periods).
Due dates: 31 July (Jan-Jun period) & 31 January (Jul-Dec period).
12% interest on late payment as per Section 9A.
"""

from django import forms
from django.urls import reverse
from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from Sapp.app.company import Company


PERIOD_CHOICES = [
    ('jan_jun', 'January – June'),
    ('jul_dec', 'July – December'),
]

RETURN_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('filed', 'Filed'),
    ('overdue', 'Overdue'),
]

# 2025 statutory rates for Haryana — update here if revised by notification
EMPLOYEE_LWF_RATE = 10
EMPLOYER_LWF_RATE = 20


# ── Model ────────────────────────────────────────────────────────────────────

class LabourWelfareFundContribution(models.Model):
    lwf_id = models.AutoField(primary_key=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    year = models.PositiveSmallIntegerField()
    contribution_period = models.CharField(max_length=10, choices=PERIOD_CHOICES)

    total_employees = models.PositiveIntegerField(default=0)
    employee_contribution = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                              help_text=f'Employee LWF @ ₹{EMPLOYEE_LWF_RATE} per employee')
    employer_contribution = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                              help_text=f'Employer LWF @ ₹{EMPLOYER_LWF_RATE} per employee')
    total_contribution = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    challan_no = models.CharField(max_length=100, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True, help_text='31 Jan or 31 Jul')
    is_late = models.BooleanField(default=False)
    late_interest_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                              help_text='12% interest on late payment (Section 9A)')

    filing_status = models.CharField(max_length=10, choices=RETURN_STATUS_CHOICES, default='pending')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='lwf_created')
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'labour_welfare_fund_contribution'
        unique_together = ('company', 'year', 'contribution_period')
        ordering = ['-year', '-contribution_period']

    def save(self, *args, **kwargs):
        self.total_contribution = round(
            float(self.employee_contribution) + float(self.employer_contribution), 2
        )
        super().save(*args, **kwargs)

    @staticmethod
    def calculate_for_employee_count(count):
        """Returns (employee_contribution, employer_contribution) for the given headcount."""
        return round(count * EMPLOYEE_LWF_RATE, 2), round(count * EMPLOYER_LWF_RATE, 2)

    def __str__(self):
        return f"LWF {self.get_contribution_period_display()} {self.year} — {self.company.company_name}"


# ── Form ─────────────────────────────────────────────────────────────────────

class LabourWelfareFundContributionForm(forms.ModelForm):
    class Meta:
        model = LabourWelfareFundContribution
        fields = ['year', 'contribution_period', 'total_employees', 'employee_contribution',
                  'employer_contribution', 'challan_no', 'payment_date', 'due_date',
                  'is_late', 'late_interest_amount', 'filing_status']
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }


# ── Helper ───────────────────────────────────────────────────────────────────

def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Views ────────────────────────────────────────────────────────────────────

@login_required
def list_lwf(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    records = LabourWelfareFundContribution.objects.filter(company=company)
    rows = [{
        'cells': [r.year, r.get_contribution_period_display(), r.total_employees,
                  r.total_contribution, r.due_date or '—', r.get_filing_status_display()],
        'actions': [{'url': reverse('alter_lwf', args=[r.lwf_id]), 'label': 'Edit', 'css': 'edit'}] +
                   ([{'url': reverse('mark_lwf_paid', args=[r.lwf_id]), 'label': 'Mark Paid'}]
                    if r.filing_status != 'filed' else []),
    } for r in records]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Punjab Labour Welfare Fund Act 1965 (Haryana)',
        'columns': ['Year', 'Period', 'Employees', 'Total Contribution', 'Due Date', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_lwf'), 'add_label': 'Add Contribution',
        'empty_message': 'No LWF contributions recorded yet.',
    })


@login_required
def add_lwf(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = LabourWelfareFundContributionForm(request.POST)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.company = company
            rec.created_by = request.user
            rec.save()
            messages.success(request, 'Labour Welfare Fund contribution recorded.')
            return redirect('list_lwf')
    else:
        from Aapp.app.employee import employee as employee_model
        emp_count = employee_model.objects.filter(CompanyID=company, is_working=True).count()
        ee, er = LabourWelfareFundContribution.calculate_for_employee_count(emp_count)
        form = LabourWelfareFundContributionForm(initial={
            'total_employees': emp_count,
            'employee_contribution': ee,
            'employer_contribution': er,
        })

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': 'Add Labour Welfare Fund Contribution',
        'cancel_url': reverse('list_lwf'),
    })


@login_required
def alter_lwf(request, lwf_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(LabourWelfareFundContribution, lwf_id=lwf_id, company=company)

    if request.method == 'POST':
        form = LabourWelfareFundContributionForm(request.POST, instance=rec)
        if form.is_valid():
            form.save()
            messages.success(request, 'LWF record updated.')
            return redirect('list_lwf')
    else:
        form = LabourWelfareFundContributionForm(instance=rec)

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': f'Edit LWF Record — {rec.get_contribution_period_display()} {rec.year}',
        'cancel_url': reverse('list_lwf'),
    })


@login_required
def mark_lwf_paid(request, lwf_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(LabourWelfareFundContribution, lwf_id=lwf_id, company=company)
    if request.method == 'POST':
        from datetime import date
        rec.payment_date = request.POST.get('payment_date') or date.today()
        rec.filing_status = 'filed'
        if rec.due_date and rec.payment_date > rec.due_date:
            rec.is_late = True
            days_late = (rec.payment_date - rec.due_date).days
            rec.late_interest_amount = round(
                float(rec.total_contribution) * 0.12 * (days_late / 365), 2
            )
        rec.save()
        messages.success(request, 'LWF contribution marked as paid.')
        return redirect('list_lwf')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Mark LWF Contribution as Paid',
        'confirm_message': f'Mark LWF contribution for <strong>{rec.get_contribution_period_display()} '
                            f'{rec.year}</strong> (₹{rec.total_contribution}) as paid?',
        'extra_fields': [{'name': 'payment_date', 'label': 'Payment Date', 'type': 'date'}],
        'cancel_url': reverse('list_lwf'),
    })
