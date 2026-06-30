from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from Sapp.app.company import Company
from Aapp.app.employee import employee
from Aapp.app.branch_department import department
from Aapp.app.attandance import MONTH_CHOICES


MATERNITY_STATUS_CHOICES = [
    ('applied',     'Applied'),
    ('approved',    'Approved'),
    ('on_leave',    'On Leave'),
    ('returned',    'Returned'),
    ('rejected',    'Rejected'),
]


# ── Model ─────────────────────────────────────────────────────────────────────

class maternity_record(models.Model):
    """
    Maternity Benefit Act 1961 — Register of Women Workers (Form A).
    Applicable to female employees only.
    """
    maternity_id            = models.AutoField(primary_key=True)
    company                 = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    employee                = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID',
                                related_name='maternity_records',
                                limit_choices_to={'gender': 'Female'})
    department              = models.ForeignKey(department, on_delete=models.SET_NULL, null=True, blank=True,
                                db_column='DepartmentID')

    # Employment details at time of application
    date_of_joining         = models.DateField(help_text='Auto-filled from employee record')
    salary_month            = models.PositiveSmallIntegerField(choices=MONTH_CHOICES,
                                help_text='Month of application')
    salary_year             = models.PositiveSmallIntegerField(help_text='Year of application')

    # Maternity details
    expected_delivery_date  = models.DateField()
    actual_delivery_date    = models.DateField(null=True, blank=True)
    maternity_leave_start   = models.DateField(help_text='Max 8 weeks before expected delivery')
    maternity_leave_end     = models.DateField(help_text='Total 26 weeks for first 2 children, 12 weeks thereafter')
    actual_return_date      = models.DateField(null=True, blank=True)

    # Benefits
    daily_wage_rate         = models.DecimalField(max_digits=10, decimal_places=2,
                                help_text='Average daily wage for benefit calculation')
    maternity_benefit_days  = models.PositiveIntegerField(default=0,
                                help_text='Number of days benefit is payable')
    maternity_benefit_amount= models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                help_text='daily_wage_rate × maternity_benefit_days')
    medical_bonus           = models.DecimalField(max_digits=10, decimal_places=2, default=3500,
                                help_text='Medical bonus ₹3500 as per Act (if no prenatal care provided)')
    nursing_breaks          = models.BooleanField(default=True,
                                help_text='Two nursing breaks per day until child is 15 months old')

    status                  = models.CharField(max_length=15, choices=MATERNITY_STATUS_CHOICES, default='applied')
    remarks                 = models.CharField(max_length=500, blank=True)
    is_paid                 = models.BooleanField(default=False)
    payment_date            = models.DateField(null=True, blank=True)

    created_by              = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='maternity_created')
    created_date            = models.DateTimeField(auto_now_add=True)
    updated_by              = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='maternity_updated')
    updated_date            = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'maternity_record'
        unique_together = ('employee', 'expected_delivery_date')
        ordering        = ['-maternity_leave_start']

    def __str__(self):
        return f"{self.employee.name} — Maternity {self.maternity_leave_start} to {self.maternity_leave_end}"

    def save(self, *args, **kwargs):
        if self.maternity_benefit_days and self.daily_wage_rate:
            self.maternity_benefit_amount = round(
                float(self.daily_wage_rate) * self.maternity_benefit_days, 2
            )
        super().save(*args, **kwargs)

    @staticmethod
    def calculate_leave_days(start, end):
        if start and end:
            return (end - start).days + 1
        return 0


class maternity_nomination(models.Model):
    """Form F (Sec 6) — nominee to receive maternity benefit if employee dies."""
    nomination_id      = models.AutoField(primary_key=True)
    company             = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    employee             = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID',
                            related_name='maternity_nominations', limit_choices_to={'gender': 'Female'})
    nominee_name           = models.CharField(max_length=255)
    relationship             = models.CharField(max_length=20, choices=[
                                ('spouse', 'Spouse'), ('son', 'Son'), ('daughter', 'Daughter'),
                                ('father', 'Father'), ('mother', 'Mother'), ('brother', 'Brother'),
                                ('sister', 'Sister'), ('other', 'Other'),
                             ])
    nominee_address           = models.TextField()
    nomination_date             = models.DateField()
    is_active                    = models.BooleanField(default=True)
    created_by                    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='mat_nominations_created')
    created_date                   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'maternity_nomination'
        ordering = ['employee']

    def __str__(self):
        return f"Maternity Nomination — {self.employee.name} → {self.nominee_name}"


# ── Helper ────────────────────────────────────────────────────────────────────

from django import forms as _mforms

class MaternityRecordForm(_mforms.ModelForm):
    class Meta:
        model = maternity_record
        fields = ['expected_delivery_date', 'maternity_leave_start', 'maternity_leave_end',
                  'daily_wage_rate', 'medical_bonus', 'remarks']
        widgets = {
            'expected_delivery_date': _mforms.DateInput(attrs={'type': 'date'}),
            'maternity_leave_start': _mforms.DateInput(attrs={'type': 'date'}),
            'maternity_leave_end': _mforms.DateInput(attrs={'type': 'date'}),
        }


def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Maternity Record Views (Form B) ──────────────────────────────────────────

@login_required
def list_maternity(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    records = maternity_record.objects.filter(company=company).select_related('employee')
    rows = [{
        'cells': [r.employee.name, r.expected_delivery_date, r.maternity_leave_start,
                  r.maternity_leave_end or '—', r.maternity_benefit_amount,
                  'Paid' if r.is_paid else 'Pending'],
        'actions': [
            {'url': reverse('update_maternity', args=[r.maternity_id]), 'label': 'Edit', 'css': 'edit'},
        ] + ([{'url': reverse('mark_maternity_paid', args=[r.maternity_id]), 'label': 'Mark Paid'}]
             if not r.is_paid else []) +
            [{'url': reverse('delete_maternity', args=[r.maternity_id]), 'label': 'Delete', 'css': 'delete'}],
    } for r in records]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Maternity Benefit Act 1961 — Maternity Register (Form B)',
        'columns': ['Employee', 'Expected Delivery', 'Leave Start', 'Leave End', 'Benefit Amount', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_maternity'), 'add_label': 'Add Maternity Record',
        'extra_links': [{'url': reverse('list_maternity_nominations'), 'label': 'Nominations (Form F)'}],
        'empty_message': 'No maternity records yet.',
    })


@login_required
def add_maternity(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    employees = employee.objects.filter(CompanyID=company, is_working=True, gender='Female').order_by('name')

    if request.method == 'POST':
        emp = get_object_or_404(employee, employeeid=request.POST.get('employee_id'),
                                 CompanyID=company, gender='Female')
        form = MaternityRecordForm(request.POST)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.company = company
            rec.employee = emp
            rec.created_by = request.user
            rec.save()
            messages.success(request, f'Maternity record created for {emp.name}.')
            return redirect('list_maternity')
    else:
        form = MaternityRecordForm()

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'employees': employees, 'company': company,
        'page_title': 'Add Maternity Record (Form B)',
        'cancel_url': reverse('list_maternity'),
    })


@login_required
def update_maternity(request, maternity_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(maternity_record, maternity_id=maternity_id, company=company)

    if request.method == 'POST':
        form = MaternityRecordForm(request.POST, instance=rec)
        if form.is_valid():
            form.save()
            messages.success(request, 'Maternity record updated.')
            return redirect('list_maternity')
    else:
        form = MaternityRecordForm(instance=rec)

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': f'Edit Maternity Record — {rec.employee.name}',
        'cancel_url': reverse('list_maternity'),
    })


@login_required
def mark_maternity_paid(request, maternity_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(maternity_record, maternity_id=maternity_id, company=company, is_paid=False)
    if request.method == 'POST':
        from datetime import date
        rec.is_paid = True
        rec.payment_date = request.POST.get('payment_date') or date.today()
        rec.save()
        messages.success(request, f'Maternity benefit marked as paid for {rec.employee.name}.')
        return redirect('list_maternity')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Mark Maternity Benefit as Paid',
        'confirm_message': f'Mark maternity benefit of '
                            f'<strong>₹{rec.maternity_benefit_amount}</strong> for '
                            f'<strong>{rec.employee.name}</strong> as paid?',
        'extra_fields': [{'name': 'payment_date', 'label': 'Payment Date', 'type': 'date'}],
        'cancel_url': reverse('list_maternity'),
    })


@login_required
def delete_maternity(request, maternity_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(maternity_record, maternity_id=maternity_id, company=company)
    if request.method == 'POST':
        rec.delete()
        messages.success(request, 'Maternity record deleted.')
        return redirect('list_maternity')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Delete Maternity Record',
        'confirm_message': f'Delete maternity record for <strong>{rec.employee.name}</strong>?',
        'cancel_url': reverse('list_maternity'),
    })


# ── Nomination Views (Form F) ────────────────────────────────────────────────

@login_required
def list_maternity_nominations(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    nominations = maternity_nomination.objects.filter(company=company).select_related('employee')
    rows = [{
        'cells': [n.employee.name, n.nominee_name, n.get_relationship_display(),
                  n.nomination_date],
        'actions': [{'url': reverse('delete_maternity_nomination', args=[n.nomination_id]),
                     'label': 'Delete', 'css': 'delete'}],
    } for n in nominations]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Maternity Benefit Act — Nominations (Form F)',
        'columns': ['Employee', 'Nominee', 'Relationship', 'Nomination Date'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_maternity_nomination'), 'add_label': 'Add Nomination',
        'empty_message': 'No maternity nominations recorded.',
    })


@login_required
def add_maternity_nomination(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    employees = employee.objects.filter(CompanyID=company, is_working=True, gender='Female').order_by('name')

    if request.method == 'POST':
        p = request.POST
        emp = get_object_or_404(employee, employeeid=p.get('employee_id'),
                                 CompanyID=company, gender='Female')
        maternity_nomination.objects.create(
            company=company, employee=emp,
            nominee_name=p.get('nominee_name'),
            relationship=p.get('relationship'),
            nominee_address=p.get('nominee_address'),
            nomination_date=p.get('nomination_date'),
            created_by=request.user,
        )
        messages.success(request, f'Nomination recorded for {emp.name}.')
        return redirect('list_maternity_nominations')

    return render(request, 'Aapp/generic/form.html', {
        'manual_fields': [
            {'name': 'nominee_name', 'label': 'Nominee Name', 'type': 'text'},
            {'name': 'relationship', 'label': 'Relationship', 'type': 'select',
             'choices': [('spouse','Spouse'),('son','Son'),('daughter','Daughter'),
                         ('father','Father'),('mother','Mother'),('other','Other')]},
            {'name': 'nominee_address', 'label': 'Nominee Address', 'type': 'textarea'},
            {'name': 'nomination_date', 'label': 'Nomination Date', 'type': 'date'},
        ],
        'employees': employees, 'company': company,
        'page_title': 'Add Maternity Nomination (Form F)',
        'cancel_url': reverse('list_maternity_nominations'),
    })


@login_required
def delete_maternity_nomination(request, nomination_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    nom = get_object_or_404(maternity_nomination, nomination_id=nomination_id, company=company)
    if request.method == 'POST':
        nom.delete()
        messages.success(request, 'Nomination deleted.')
        return redirect('list_maternity_nominations')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Delete Maternity Nomination',
        'confirm_message': f'Delete nomination for <strong>{nom.employee.name}</strong> '
                            f'→ {nom.nominee_name}?',
        'cancel_url': reverse('list_maternity_nominations'),
    })
