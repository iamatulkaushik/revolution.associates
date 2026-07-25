from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from Sapp.app.company import Company
from Aapp.app.employee import employee


RELATIONSHIP_CHOICES = [
    ('spouse',          'Spouse'),
    ('son',             'Son'),
    ('daughter',        'Daughter'),
    ('father',          'Father'),
    ('mother',          'Mother'),
    ('brother',         'Brother'),
    ('sister',          'Sister'),
    ('other',           'Other'),
]

GRATUITY_REASON_CHOICES = [
    ('superannuation',  'Superannuation'),
    ('retirement',      'Retirement'),
    ('resignation',     'Resignation'),
    ('death',           'Death'),
    ('disablement',     'Disablement'),
    ('termination',     'Termination'),
]


# ── Models ────────────────────────────────────────────────────────────────────

class gratuity_nominee(models.Model):
    nominee_id      = models.AutoField(primary_key=True)
    company         = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    employee        = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID', related_name='nominees')
    nominee_name    = models.CharField(max_length=255)
    relationship    = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    address         = models.TextField()
    share_percent   = models.DecimalField(max_digits=5, decimal_places=2,
                        help_text='Share percentage (all nominees must total 100%)')
    date_of_birth   = models.DateField(null=True, blank=True)
    gender          = models.CharField(max_length=10, choices=[('Male','Male'),('Female','Female'),('Other','Other')])
    aadhar_number   = models.CharField(max_length=12, blank=True,
                        help_text='For identity verification (Form F — Gratuity Act)')
    pan_number      = models.CharField(max_length=10, blank=True)
    bank_account    = models.CharField(max_length=20, blank=True)
    bank_ifsc       = models.CharField(max_length=11, blank=True)
    bank_name       = models.CharField(max_length=255, blank=True)
    is_minor        = models.BooleanField(default=False,
                        help_text='If minor, guardian details required as per Form F')
    guardian_name   = models.CharField(max_length=255, blank=True)
    guardian_relationship = models.CharField(max_length=100, blank=True)
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='nominees_created')
    created_date    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gratuity_nominee'
        ordering = ['employee', 'nominee_name']

    def __str__(self):
        return f"{self.employee.employeecode} — {self.nominee_name} ({self.get_relationship_display()})"


class gratuity_record(models.Model):
    gratuity_id         = models.AutoField(primary_key=True)
    company             = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    employee            = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID', related_name='gratuity')

    # Service details
    date_of_joining     = models.DateField(help_text='Auto-filled from employee record')
    date_of_leaving     = models.DateField(help_text='Auto-filled from employee record')
    years_of_service    = models.DecimalField(max_digits=5, decimal_places=2,
                            help_text='Calculated: min 5 years required for eligibility')

    # Salary basis
    basic_salary        = models.DecimalField(max_digits=10, decimal_places=2,
                            help_text='Last drawn basic + DA (basis for gratuity calculation)')
    da                  = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Gratuity calculation: (Basic+DA) × 15/26 × Years of Service
    gratuity_amount     = models.DecimalField(max_digits=12, decimal_places=2,
                            help_text='Formula: (Basic+DA) × 15/26 × Years')
    reason              = models.CharField(max_length=30, choices=GRATUITY_REASON_CHOICES)
    remarks             = models.CharField(max_length=500, blank=True)

    is_paid             = models.BooleanField(default=False)
    payment_date        = models.DateField(null=True, blank=True)
    created_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='gratuity_created')
    created_date        = models.DateTimeField(auto_now_add=True)
    updated_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='gratuity_updated')
    updated_date        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gratuity_record'
        unique_together = ('employee', 'date_of_leaving')
        ordering = ['-date_of_leaving']

    def __str__(self):
        return f"{self.employee.employeecode} — Gratuity ₹{self.gratuity_amount}"

    @staticmethod
    def calculate_gratuity(basic, da, years):
        return round((float(basic) + float(da)) * 15 / 26 * float(years), 2)


class gratuity_employer_notice(models.Model):
    """
    Form A — Notice of Opening (Sec 4A, within 30 days of opening).
    Form B — Notice of Change (within 30 days of change).
    Form C — Notice of Closure (within 60 days before closure).
    Form D — Notice of Exclusion of Husband from Family (female employee).
    """
    notice_id           = models.AutoField(primary_key=True)
    company              = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    notice_type           = models.CharField(max_length=10, choices=[
                                ('A', 'Form A — Opening'), ('B', 'Form B — Change'),
                                ('C', 'Form C — Closure'), ('D', 'Form D — Husband Exclusion'),
                             ])
    notice_date            = models.DateField()
    submitted_to             = models.CharField(max_length=255, blank=True,
                                help_text='Controlling Authority the notice was submitted to')
    acknowledgement_no        = models.CharField(max_length=100, blank=True)
    remarks                    = models.CharField(max_length=500, blank=True)
    created_by                  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='gratuity_notices_created')
    created_date                 = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gratuity_employer_notice'
        ordering = ['-notice_date']

    def __str__(self):
        return f"Gratuity {self.get_notice_type_display()} — {self.company.company_name} {self.notice_date}"


class gratuity_payment_notice(models.Model):
    """Form I — Notice of Payment (Sec 7(2), within 30 days). Form J — Notice of Rejection."""
    notice_id            = models.AutoField(primary_key=True)
    company               = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    employee               = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID',
                                related_name='gratuity_notices')
    gratuity_record_ref      = models.ForeignKey(gratuity_record, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='payment_notices')
    notice_type                = models.CharField(max_length=5, choices=[
                                ('I', 'Form I — Payment Notice'), ('J', 'Form J — Rejection Notice'),
                             ])
    notice_date                  = models.DateField()
    gratuity_amount                = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_due_date                 = models.DateField(null=True, blank=True)
    rejection_reason                   = models.TextField(blank=True)
    created_by                          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='gratuity_payment_notices_created')
    created_date                         = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gratuity_payment_notice'
        ordering = ['-notice_date']

    def __str__(self):
        return f"Gratuity {self.get_notice_type_display()} — {self.employee.name}"


# ── Helper ────────────────────────────────────────────────────────────────────

from django import forms as _gforms

class GratuityNomineeForm(_gforms.ModelForm):
    class Meta:
        model = gratuity_nominee
        fields = ['nominee_name', 'relationship', 'share_percent', 'date_of_birth',
                  'address', 'aadhar_number', 'pan_number', 'bank_account',
                  'bank_ifsc', 'bank_name', 'is_minor', 'guardian_name',
                  'guardian_relationship']
        widgets = {'date_of_birth': _gforms.DateInput(attrs={'type': 'date'})}

class GratuityRecordForm(_gforms.ModelForm):
    class Meta:
        model = gratuity_record
        fields = ['date_of_joining', 'date_of_leaving', 'basic_salary', 'da', 'reason']
        widgets = {
            'date_of_joining': _gforms.DateInput(attrs={'type': 'date'}),
            'date_of_leaving': _gforms.DateInput(attrs={'type': 'date'}),
        }


def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Nominee Views (Form E) ────────────────────────────────────────────────────

@login_required
def list_nominees(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')
    nominees = gratuity_nominee.objects.filter(company=company).select_related('employee')
    rows = [{
        'cells': [n.employee.name, n.nominee_name, n.get_relationship_display(),
                  f'{n.share_percent}%', n.aadhar_number or '—'],
        'actions': [
            {'url': reverse('update_nominee', args=[n.nominee_id]), 'label': 'Edit', 'css': 'edit'},
            {'url': reverse('delete_nominee', args=[n.nominee_id]), 'label': 'Delete', 'css': 'delete'},
        ],
    } for n in nominees]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Gratuity Act 1972 — Nominee Register (Form E)',
        'columns': ['Employee', 'Nominee', 'Relationship', 'Share %', 'Aadhaar'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_nominee'), 'add_label': 'Add Nominee',
        'empty_message': 'No nominees registered yet.',
    })


@login_required
def add_nominee(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    employees = employee.objects.filter(CompanyID=company, is_working=True).order_by('name')

    if request.method == 'POST':
        emp = get_object_or_404(employee, employeeid=request.POST.get('employee_id'), CompanyID=company)
        form = GratuityNomineeForm(request.POST)
        if form.is_valid():
            nom = form.save(commit=False)
            nom.company = company
            nom.employee = emp
            nom.created_by = request.user
            nom.save()
            messages.success(request, f'Nominee added for {emp.name}.')
            return redirect('list_nominees')
    else:
        form = GratuityNomineeForm()

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'employees': employees, 'company': company,
        'page_title': 'Add Gratuity Nominee (Form E)',
        'cancel_url': reverse('list_nominees'),
    })


@login_required
def update_nominee(request, nominee_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    nom = get_object_or_404(gratuity_nominee, nominee_id=nominee_id, company=company)

    if request.method == 'POST':
        form = GratuityNomineeForm(request.POST, instance=nom)
        if form.is_valid():
            form.save()
            messages.success(request, 'Nominee updated.')
            return redirect('list_nominees')
    else:
        form = GratuityNomineeForm(instance=nom)

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': f'Edit Nominee — {nom.nominee_name}',
        'cancel_url': reverse('list_nominees'),
    })


@login_required
def delete_nominee(request, nominee_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    nom = get_object_or_404(gratuity_nominee, nominee_id=nominee_id, company=company)
    if request.method == 'POST':
        nom.delete()
        messages.success(request, 'Nominee deleted.')
        return redirect('list_nominees')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Delete Nominee',
        'confirm_message': f'Delete nominee <strong>{nom.nominee_name}</strong> for {nom.employee.name}?',
        'cancel_url': reverse('list_nominees'),
    })


# ── Gratuity Record Views (Form F-H) ─────────────────────────────────────────

@login_required
def list_gratuity(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')
    records = gratuity_record.objects.filter(company=company).select_related('employee')
    rows = [{
        'cells': [r.employee.name, r.date_of_joining, r.date_of_leaving,
                  r.years_of_service, r.gratuity_amount,
                  'Paid' if r.is_paid else 'Pending'],
        'actions': [
            {'url': reverse('add_payment_notice', args=[r.gratuity_id]), 'label': 'Issue Notice'},
        ] + ([{'url': reverse('mark_gratuity_paid', args=[r.gratuity_id]), 'label': 'Mark Paid'}]
             if not r.is_paid else []) +
            ([{'url': reverse('delete_gratuity', args=[r.gratuity_id]), 'label': 'Delete', 'css': 'delete'}]
             if not r.is_paid else []),
    } for r in records]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Gratuity Act 1972 — Gratuity Register (Form F)',
        'columns': ['Employee', 'Date of Joining', 'Date of Leaving', 'Years', 'Gratuity Amount', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_gratuity'), 'add_label': 'Calculate Gratuity',
        'empty_message': 'No gratuity records yet.',
    })


@login_required
def add_gratuity(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    employees = employee.objects.filter(CompanyID=company).order_by('name')

    if request.method == 'POST':
        emp = get_object_or_404(employee, employeeid=request.POST.get('employee_id'), CompanyID=company)
        form = GratuityRecordForm(request.POST)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.company = company
            rec.employee = emp
            rec.gratuity_amount = gratuity_record.calculate_gratuity(
                rec.basic_salary, rec.da, rec.years_of_service
            ) if hasattr(rec, 'years_of_service') else 0
            rec.created_by = request.user
            rec.save()
            messages.success(request, f'Gratuity calculated for {emp.name}: ₹{rec.gratuity_amount}')
            return redirect('list_gratuity')
    else:
        form = GratuityRecordForm()

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'employees': employees, 'company': company,
        'page_title': 'Calculate Gratuity (Gratuity Act — Form F)',
        'cancel_url': reverse('list_gratuity'),
    })


@login_required
def mark_gratuity_paid(request, gratuity_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    rec = get_object_or_404(gratuity_record, gratuity_id=gratuity_id, company=company, is_paid=False)
    if request.method == 'POST':
        from datetime import date
        rec.is_paid = True
        rec.payment_date = request.POST.get('payment_date') or date.today()
        rec.save()
        messages.success(request, f'Gratuity marked as paid for {rec.employee.name}.')
        return redirect('list_gratuity')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Mark Gratuity as Paid',
        'confirm_message': f'Mark gratuity of <strong>₹{rec.gratuity_amount}</strong> for '
                            f'<strong>{rec.employee.name}</strong> as paid?',
        'extra_fields': [{'name': 'payment_date', 'label': 'Payment Date', 'type': 'date'}],
        'cancel_url': reverse('list_gratuity'),
    })


@login_required
def delete_gratuity(request, gratuity_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    rec = get_object_or_404(gratuity_record, gratuity_id=gratuity_id, company=company, is_paid=False)
    if request.method == 'POST':
        rec.delete()
        messages.success(request, 'Gratuity record deleted.')
        return redirect('list_gratuity')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Delete Gratuity Record',
        'confirm_message': f'Delete gratuity record for <strong>{rec.employee.name}</strong>?',
        'cancel_url': reverse('list_gratuity'),
    })


# ── Employer Notice Views (Form A-D) ─────────────────────────────────────────

@login_required
def list_employer_notices(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')
    notices = gratuity_employer_notice.objects.filter(company=company)
    rows = [{
        'cells': [n.get_notice_type_display(), n.notice_date, n.submitted_to or '—',
                  n.acknowledgement_no or '—'],
        'actions': [],
    } for n in notices]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Gratuity Act — Employer Notices (Form A/B/C/D)',
        'columns': ['Notice Type', 'Date', 'Submitted To', 'Ack. No.'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_employer_notice'), 'add_label': 'Add Notice',
        'empty_message': 'No employer notices recorded.',
    })


@login_required
def add_employer_notice(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        p = request.POST
        gratuity_employer_notice.objects.create(
            company=company,
            notice_type=p.get('notice_type'),
            notice_date=p.get('notice_date'),
            submitted_to=p.get('submitted_to', ''),
            acknowledgement_no=p.get('acknowledgement_no', ''),
            remarks=p.get('remarks', ''),
            created_by=request.user,
        )
        messages.success(request, 'Employer notice recorded.')
        return redirect('list_employer_notices')

    NOTICE_TYPES = [('A','Form A — Opening'),('B','Form B — Change'),
                    ('C','Form C — Closure'),('D','Form D — Husband Exclusion')]
    return render(request, 'Aapp/generic/form.html', {
        'manual_fields': [
            {'name': 'notice_type', 'label': 'Notice Type', 'type': 'select', 'choices': NOTICE_TYPES},
            {'name': 'notice_date', 'label': 'Notice Date', 'type': 'date'},
            {'name': 'submitted_to', 'label': 'Submitted To', 'type': 'text'},
            {'name': 'acknowledgement_no', 'label': 'Acknowledgement No.', 'type': 'text'},
            {'name': 'remarks', 'label': 'Remarks', 'type': 'textarea'},
        ],
        'company': company,
        'page_title': 'Add Employer Notice (Form A/B/C/D)',
        'cancel_url': reverse('list_employer_notices'),
    })


# ── Payment Notice Views (Form I / J) ────────────────────────────────────────

@login_required
def list_payment_notices(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')
    notices = gratuity_payment_notice.objects.filter(company=company).select_related('employee')
    rows = [{
        'cells': [n.employee.name, n.get_notice_type_display(), n.notice_date,
                  n.gratuity_amount, n.payment_due_date or '—'],
        'actions': [],
    } for n in notices]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Gratuity Act — Payment / Rejection Notices (Form I / J)',
        'columns': ['Employee', 'Notice Type', 'Date', 'Gratuity Amount', 'Payment Due'],
        'rows': rows, 'company': company,
        'empty_message': 'No payment notices issued yet.',
    })


@login_required
def add_payment_notice(request, gratuity_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    rec = get_object_or_404(gratuity_record, gratuity_id=gratuity_id, company=company)

    if request.method == 'POST':
        p = request.POST
        gratuity_payment_notice.objects.create(
            company=company,
            employee=rec.employee,
            gratuity_record_ref=rec,
            notice_type=p.get('notice_type'),
            notice_date=p.get('notice_date'),
            gratuity_amount=p.get('gratuity_amount', rec.gratuity_amount),
            payment_due_date=p.get('payment_due_date') or None,
            rejection_reason=p.get('rejection_reason', ''),
            created_by=request.user,
        )
        messages.success(request, f'Notice issued for {rec.employee.name}.')
        return redirect('list_payment_notices')

    return render(request, 'Aapp/generic/form.html', {
        'manual_fields': [
            {'name': 'notice_type', 'label': 'Notice Type', 'type': 'select',
             'choices': [('I','Form I — Payment Notice'),('J','Form J — Rejection Notice')]},
            {'name': 'notice_date', 'label': 'Notice Date', 'type': 'date'},
            {'name': 'gratuity_amount', 'label': 'Gratuity Amount (₹)', 'type': 'text',
             'value': rec.gratuity_amount},
            {'name': 'payment_due_date', 'label': 'Payment Due Date', 'type': 'date'},
            {'name': 'rejection_reason', 'label': 'Rejection Reason (Form J only)', 'type': 'textarea'},
        ],
        'company': company, 'rec': rec,
        'page_title': f'Issue Notice (Form I/J) — {rec.employee.name}',
        'cancel_url': reverse('list_payment_notices'),
    })
