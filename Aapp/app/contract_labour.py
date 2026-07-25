"""
Contract Labour (Regulation & Abolition) Act, 1970 — remaining statutory forms.

Already covered elsewhere in the codebase:
    Aapp/app/contractor.py   -> contractor (Form IV — Register of Contractors)
                              -> contractor_worker (Form XII — Muster Roll concept)
                              -> contractor_payment

This file adds the forms NOT yet covered:
    Form I & II  -> ContractLabourRegistration   (Principal Employer registration)
    Form XIII    -> ContractEmploymentCard       (issued to each contract worker)
    Form XIV     -> ContractServiceCertificate   (issued on termination)
    Form 20(CL)  -> ContractLabourHalfYearlyReturn
"""

from django import forms
from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from Sapp.app.company import Company
from Aapp.app.employee import employee
from Aapp.app.contractor import contractor


HALF_YEAR_CHOICES = [
    ('jan_jun', 'January – June'),
    ('jul_dec', 'July – December'),
]

RETURN_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('filed',   'Filed'),
    ('overdue', 'Overdue'),
]


# ── Models ───────────────────────────────────────────────────────────────────

class ContractLabourRegistration(models.Model):
    """Form I (Application) & Form II (Certificate) — Section 7."""
    reg_id                  = models.AutoField(primary_key=True)
    company                 = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')

    registration_cert_no    = models.CharField(max_length=50, blank=True,
                                help_text='Registration Certificate No. (Form II)')
    registration_date       = models.DateField(null=True, blank=True)
    registration_authority  = models.CharField(max_length=255, blank=True,
                                help_text='Registering Officer name & designation')
    establishment_name      = models.CharField(max_length=255,
                                help_text='Name of establishment as Principal Employer (Form I)')
    nature_of_work          = models.TextField(help_text='Nature of work for contract labour (Form I)')
    max_contract_workers    = models.PositiveIntegerField(default=0,
                                help_text='Maximum number of contract workers (Form I — Sec 7)')
    is_active                = models.BooleanField(default=True)

    created_by              = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='cl_reg_created')
    created_date            = models.DateTimeField(auto_now_add=True)
    updated_date            = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'contract_labour_registration'
        unique_together  = ('company', 'registration_cert_no')
        ordering         = ['-registration_date']

    def __str__(self):
        return f"CL Reg {self.registration_cert_no or '(unregistered)'} — {self.company.company_name}"


class ContractEmploymentCard(models.Model):
    """Form XIII (Rule 62) — issued to each contract worker within 3 days of employment."""
    card_id                 = models.AutoField(primary_key=True)
    company                 = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    contractor              = models.ForeignKey(contractor, on_delete=models.CASCADE, related_name='employment_cards')
    employee                = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID',
                                related_name='employment_cards')

    card_number              = models.CharField(max_length=50, blank=True)
    token_number              = models.CharField(max_length=50, blank=True,
                                help_text='Token / badge number issued to worker (Rule 62(2))')
    work_description         = models.TextField(help_text='Nature of work assigned (Form XIII)')
    work_site                = models.CharField(max_length=255)
    wage_rate                = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    issue_date                = models.DateField()
    validity_date              = models.DateField(null=True, blank=True)

    created_by               = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='employment_cards_created')
    created_date              = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'contract_employment_card'
        ordering = ['-issue_date']

    def __str__(self):
        return f"Card {self.card_number or self.card_id} — {self.employee.name}"


class ContractServiceCertificate(models.Model):
    """Form XIV (Rule 63) — issued on the day of termination."""
    cert_id                  = models.AutoField(primary_key=True)
    company                  = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    contractor               = models.ForeignKey(contractor, on_delete=models.CASCADE, related_name='service_certificates')
    employee                 = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID',
                                related_name='service_certificates')

    work_description          = models.TextField()
    work_site                 = models.CharField(max_length=255)
    date_of_employment         = models.DateField()
    date_of_termination        = models.DateField()
    reason_for_termination     = models.CharField(max_length=255, blank=True)
    last_wage_paid              = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    certificate_date            = models.DateField()

    created_by                = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='service_certs_created')
    created_date               = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'contract_service_certificate'
        ordering = ['-certificate_date']

    def __str__(self):
        return f"Service Cert — {self.employee.name} ({self.date_of_termination})"


class ContractLabourHalfYearlyReturn(models.Model):
    """Form 20(CL) (Rule 81(1)) — due within 30 days of close of half year."""
    return_id                = models.AutoField(primary_key=True)
    company                  = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    contractor                = models.ForeignKey(contractor, on_delete=models.CASCADE, related_name='halfyearly_returns')
    year                       = models.PositiveSmallIntegerField()
    half_year                  = models.CharField(max_length=10, choices=HALF_YEAR_CHOICES)

    total_workers_employed      = models.PositiveIntegerField(default=0)
    total_man_days               = models.PositiveIntegerField(default=0)
    total_wages_paid              = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_overtime_hours           = models.PositiveIntegerField(default=0)
    total_overtime_wages            = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    filing_status              = models.CharField(max_length=10, choices=RETURN_STATUS_CHOICES, default='pending')
    filed_date                  = models.DateField(null=True, blank=True)
    acknowledgement_no           = models.CharField(max_length=100, blank=True)

    created_by                 = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='cl_returns_created')
    created_date                = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'contract_labour_halfyearly_return'
        unique_together  = ('contractor', 'year', 'half_year')
        ordering         = ['-year', '-half_year']

    def __str__(self):
        return f"CL Return {self.get_half_year_display()} {self.year} — {self.contractor.contractor_name}"


# ── Forms ────────────────────────────────────────────────────────────────────

class ContractLabourRegistrationForm(forms.ModelForm):
    class Meta:
        model = ContractLabourRegistration
        fields = ['registration_cert_no', 'registration_date', 'registration_authority',
                  'establishment_name', 'nature_of_work', 'max_contract_workers']
        widgets = {'registration_date': forms.DateInput(attrs={'type': 'date'})}


class ContractEmploymentCardForm(forms.ModelForm):
    class Meta:
        model = ContractEmploymentCard
        fields = ['employee', 'card_number', 'token_number', 'work_description',
                  'work_site', 'wage_rate', 'issue_date', 'validity_date']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'validity_date': forms.DateInput(attrs={'type': 'date'}),
        }


class ContractServiceCertificateForm(forms.ModelForm):
    class Meta:
        model = ContractServiceCertificate
        fields = ['employee', 'work_description', 'work_site', 'date_of_employment',
                  'date_of_termination', 'reason_for_termination', 'last_wage_paid', 'certificate_date']
        widgets = {
            'date_of_employment': forms.DateInput(attrs={'type': 'date'}),
            'date_of_termination': forms.DateInput(attrs={'type': 'date'}),
            'certificate_date': forms.DateInput(attrs={'type': 'date'}),
        }


class ContractLabourHalfYearlyReturnForm(forms.ModelForm):
    class Meta:
        model = ContractLabourHalfYearlyReturn
        fields = ['year', 'half_year', 'total_workers_employed', 'total_man_days',
                  'total_wages_paid', 'total_overtime_hours', 'total_overtime_wages',
                  'filing_status', 'filed_date', 'acknowledgement_no']
        widgets = {'filed_date': forms.DateInput(attrs={'type': 'date'})}


# ── Helper ───────────────────────────────────────────────────────────────────

def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Registration Views ──────────────────────────────────────────────────────

@login_required
def list_cl_registration(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')
    registrations = ContractLabourRegistration.objects.filter(company=company)
    rows = [{
        'cells': [r.registration_cert_no or '—', r.establishment_name, r.registration_date,
                  r.max_contract_workers, 'Active' if r.is_active else 'Inactive'],
        'actions': [{'url': reverse('alter_cl_registration', args=[r.reg_id]), 'label': 'Edit', 'css': 'edit'}],
    } for r in registrations]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Contract Labour Act 1970 — Registration (Form I & II)',
        'columns': ['Cert. No.', 'Establishment', 'Reg. Date', 'Max Workers', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('create_cl_registration'), 'add_label': 'Add Registration',
        'empty_message': 'No registration recorded yet.',
    })


@login_required
def create_cl_registration(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        form = ContractLabourRegistrationForm(request.POST)
        if form.is_valid():
            reg = form.save(commit=False)
            reg.company = company
            reg.created_by = request.user
            reg.save()
            messages.success(request, 'Contract Labour registration recorded.')
            return redirect('list_cl_registration')
    else:
        form = ContractLabourRegistrationForm()

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': 'Register Establishment (Contract Labour Act — Form I)',
        'cancel_url': reverse('list_cl_registration'),
    })


@login_required
def alter_cl_registration(request, reg_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    reg = get_object_or_404(ContractLabourRegistration, reg_id=reg_id, company=company)

    if request.method == 'POST':
        form = ContractLabourRegistrationForm(request.POST, instance=reg)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration updated.')
            return redirect('list_cl_registration')
    else:
        form = ContractLabourRegistrationForm(instance=reg)

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': f'Edit Registration — {reg.establishment_name}',
        'cancel_url': reverse('list_cl_registration'),
    })


# ── Employment Card Views (Form XIII) ────────────────────────────────────────

@login_required
def list_employment_cards(request, contractor_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    con = get_object_or_404(contractor, contractor_id=contractor_id, company=company)
    cards = ContractEmploymentCard.objects.filter(contractor=con).select_related('employee')
    rows = [{
        'cells': [c.card_number or '—', c.employee.name, c.work_site, c.wage_rate, c.issue_date],
        'actions': [],
    } for c in cards]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': f'Employment Cards (Form XIII) — {con.contractor_name}',
        'columns': ['Card No.', 'Employee', 'Work Site', 'Wage Rate', 'Issue Date'],
        'rows': rows, 'company': company,
        'add_url': reverse('create_employment_card', args=[contractor_id]), 'add_label': 'Issue Employment Card',
        'empty_message': 'No employment cards issued yet.',
    })


@login_required
def create_employment_card(request, contractor_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    con = get_object_or_404(contractor, contractor_id=contractor_id, company=company)

    if request.method == 'POST':
        form = ContractEmploymentCardForm(request.POST)
        if form.is_valid():
            card = form.save(commit=False)
            card.contractor = con
            card.company = company
            card.created_by = request.user
            card.save()
            messages.success(request, f'Employment card issued for {card.employee.name}.')
            return redirect('list_employment_cards', contractor_id=contractor_id)
    else:
        form = ContractEmploymentCardForm()
        form.fields['employee'].queryset = employee.objects.filter(CompanyID=company, is_working=True)

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company, 'con': con,
        'page_title': f'Issue Employment Card (Form XIII) — {con.contractor_name}',
        'cancel_url': reverse('list_employment_cards', args=[contractor_id]),
    })


# ── Service Certificate Views (Form XIV) ─────────────────────────────────────

@login_required
def list_service_certificates(request, contractor_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    con = get_object_or_404(contractor, contractor_id=contractor_id, company=company)
    certs = ContractServiceCertificate.objects.filter(contractor=con).select_related('employee')
    rows = [{
        'cells': [c.employee.name, c.date_of_employment, c.date_of_termination,
                  c.reason_for_termination or '—', c.last_wage_paid],
        'actions': [],
    } for c in certs]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': f'Service Certificates (Form XIV) — {con.contractor_name}',
        'columns': ['Employee', 'Employed From', 'Terminated On', 'Reason', 'Last Wage'],
        'rows': rows, 'company': company,
        'add_url': reverse('create_service_certificate', args=[contractor_id]), 'add_label': 'Issue Service Certificate',
        'empty_message': 'No service certificates issued yet.',
    })


@login_required
def create_service_certificate(request, contractor_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    con = get_object_or_404(contractor, contractor_id=contractor_id, company=company)

    if request.method == 'POST':
        form = ContractServiceCertificateForm(request.POST)
        if form.is_valid():
            cert = form.save(commit=False)
            cert.contractor = con
            cert.company = company
            cert.created_by = request.user
            cert.save()
            messages.success(request, f'Service certificate issued for {cert.employee.name}.')
            return redirect('list_service_certificates', contractor_id=contractor_id)
    else:
        form = ContractServiceCertificateForm()
        form.fields['employee'].queryset = employee.objects.filter(CompanyID=company)

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company, 'con': con,
        'page_title': f'Issue Service Certificate (Form XIV) — {con.contractor_name}',
        'cancel_url': reverse('list_service_certificates', args=[contractor_id]),
    })


# ── Half-Yearly Return Views (Form 20(CL)) ──────────────────────────────────

@login_required
def list_cl_returns(request, contractor_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    con = get_object_or_404(contractor, contractor_id=contractor_id, company=company)
    returns = ContractLabourHalfYearlyReturn.objects.filter(contractor=con)
    rows = [{
        'cells': [r.year, r.get_half_year_display(), r.total_workers_employed, r.total_man_days,
                  r.total_wages_paid, r.get_filing_status_display()],
        'actions': [{'url': reverse('alter_cl_return', args=[r.return_id]), 'label': 'Edit', 'css': 'edit'}],
    } for r in returns]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': f'Half-Yearly Return (Form 20(CL)) — {con.contractor_name}',
        'columns': ['Year', 'Period', 'Workers', 'Man-Days', 'Wages Paid', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('create_cl_return', args=[contractor_id]), 'add_label': 'Add Half-Yearly Return',
        'empty_message': 'No half-yearly returns filed yet.',
    })


@login_required
def create_cl_return(request, contractor_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    con = get_object_or_404(contractor, contractor_id=contractor_id, company=company)

    if request.method == 'POST':
        form = ContractLabourHalfYearlyReturnForm(request.POST)
        if form.is_valid():
            ret = form.save(commit=False)
            ret.contractor = con
            ret.company = company
            ret.created_by = request.user
            ret.save()
            messages.success(request, 'Half-yearly return recorded.')
            return redirect('list_cl_returns', contractor_id=contractor_id)
    else:
        form = ContractLabourHalfYearlyReturnForm()

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company, 'con': con,
        'page_title': f'Add Half-Yearly Return (Form 20(CL)) — {con.contractor_name}',
        'cancel_url': reverse('list_cl_returns', args=[contractor_id]),
    })


@login_required
def alter_cl_return(request, return_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    ret = get_object_or_404(ContractLabourHalfYearlyReturn, return_id=return_id, company=company)

    if request.method == 'POST':
        form = ContractLabourHalfYearlyReturnForm(request.POST, instance=ret)
        if form.is_valid():
            form.save()
            messages.success(request, 'Return updated.')
            return redirect('list_cl_returns', contractor_id=ret.contractor.contractor_id)
    else:
        form = ContractLabourHalfYearlyReturnForm(instance=ret)

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': f'Edit Half-Yearly Return — {ret.contractor.contractor_name} ({ret.year})',
        'cancel_url': reverse('list_cl_returns', args=[ret.contractor.contractor_id]),
    })
