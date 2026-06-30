from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from Sapp.app.company import Company
from Aapp.app.employee import employee


PAYMENT_SCHEDULE_CHOICES = [
    ('weekly',      'Weekly'),
    ('fortnightly', 'Fortnightly'),
    ('monthly',     'Monthly'),
    ('milestone',   'Milestone Based'),
    ('on_completion','On Completion'),
]

CONTRACT_STATUS_CHOICES = [
    ('active',      'Active'),
    ('completed',   'Completed'),
    ('terminated',  'Terminated'),
    ('suspended',   'Suspended'),
]


# ── Models ────────────────────────────────────────────────────────────────────

class contractor(models.Model):
    contractor_id       = models.AutoField(primary_key=True)
    company             = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID',
                            help_text='Principal Employer company')
    principal_employer  = models.CharField(max_length=255,
                            help_text='Name of principal employer as per Contract Labour Act Form XII')

    # Contractor identity
    contractor_name     = models.CharField(max_length=255)
    contractor_license_no = models.CharField(max_length=50, blank=True,
                            help_text='License No. under Contract Labour (R&A) Act 1970')
    contractor_address  = models.TextField(blank=True)
    contractor_mobile   = models.CharField(max_length=15, blank=True)
    contractor_email    = models.EmailField(blank=True)
    contractor_pan      = models.CharField(max_length=10, blank=True)
    contractor_gstin    = models.CharField(max_length=15, blank=True)

    # Contract details
    work_description    = models.TextField(help_text='Nature of work as per Form XII')
    contract_start_date = models.DateField()
    contract_end_date   = models.DateField()
    contract_amount     = models.DecimalField(max_digits=15, decimal_places=2)
    payment_schedule    = models.CharField(max_length=20, choices=PAYMENT_SCHEDULE_CHOICES)
    reason_for_contract = models.CharField(max_length=500, blank=True)
    status              = models.CharField(max_length=20, choices=CONTRACT_STATUS_CHOICES, default='active')

    # Compliance
    max_contract_workers = models.PositiveIntegerField(default=0,
                            help_text='Max number of contract workers deployed (Form XII)')
    worksite_address    = models.TextField(blank=True)

    created_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='contractors_created')
    created_date        = models.DateTimeField(auto_now_add=True)
    updated_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='contractors_updated')
    updated_date        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'contractor'
        ordering = ['-contract_start_date']

    def __str__(self):
        return f"{self.contractor_name} — {self.company.company_name}"


class contractor_payment(models.Model):
    payment_id          = models.AutoField(primary_key=True)
    contractor          = models.ForeignKey(contractor, on_delete=models.CASCADE, related_name='payments')
    company             = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    salary_month        = models.PositiveSmallIntegerField()
    salary_year         = models.PositiveSmallIntegerField()
    payment_amount      = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date        = models.DateField()
    payment_reference   = models.CharField(max_length=100, blank=True)
    remarks             = models.CharField(max_length=500, blank=True)
    created_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='contractor_payments_created')
    created_date        = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'contractor_payment'
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.contractor.contractor_name} — ₹{self.payment_amount} on {self.payment_date}"


class contractor_worker(models.Model):
    """Links existing employees deployed under a contractor (Form XIII)."""
    cw_id               = models.AutoField(primary_key=True)
    contractor          = models.ForeignKey(contractor, on_delete=models.CASCADE, related_name='workers')
    company             = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    employee            = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID',
                            related_name='contractor_deployments')
    deployment_start    = models.DateField()
    deployment_end      = models.DateField(null=True, blank=True)
    work_description    = models.CharField(max_length=255, blank=True)
    created_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='cw_created')
    created_date        = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'contractor_worker'
        unique_together = ('contractor', 'employee', 'deployment_start')
        ordering        = ['-deployment_start']

    def __str__(self):
        return f"{self.employee.employeecode} under {self.contractor.contractor_name}"


# ── Helper ────────────────────────────────────────────────────────────────────

from django import forms as _cforms

class ContractorForm(_cforms.ModelForm):
    class Meta:
        model = contractor
        fields = ['contractor_name', 'contractor_license_no', 'contractor_address',
                  'contractor_mobile', 'contractor_email', 'contractor_pan',
                  'work_description', 'contract_start_date', 'contract_end_date',
                  'contract_amount', 'max_contract_workers', 'worksite_address', 'status']
        widgets = {
            'contract_start_date': _cforms.DateInput(attrs={'type': 'date'}),
            'contract_end_date': _cforms.DateInput(attrs={'type': 'date'}),
        }

class ContractorWorkerForm(_cforms.ModelForm):
    class Meta:
        model = contractor_worker
        fields = ['employee', 'deployment_start', 'deployment_end', 'work_description']
        widgets = {
            'deployment_start': _cforms.DateInput(attrs={'type': 'date'}),
            'deployment_end': _cforms.DateInput(attrs={'type': 'date'}),
        }

class ContractorPaymentForm(_cforms.ModelForm):
    class Meta:
        model = contractor_payment
        fields = ['salary_month', 'salary_year', 'payment_amount',
                  'payment_date', 'payment_reference', 'remarks']
        widgets = {'payment_date': _cforms.DateInput(attrs={'type': 'date'})}


def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Contractor Views ─────────────────────────────────────────────────────────

@login_required
def list_contractors(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    contractors = contractor.objects.filter(company=company)
    rows = [{
        'cells': [c.contractor_name, c.contractor_license_no or '—', c.work_description[:50],
                  c.max_contract_workers, c.contract_end_date or '—',
                  c.status],
        'actions': [
            {'url': reverse('update_contractor', args=[c.contractor_id]), 'label': 'Edit', 'css': 'edit'},
            {'url': reverse('list_contractor_workers', args=[c.contractor_id]), 'label': 'Workers'},
            {'url': reverse('add_contractor_payment', args=[c.contractor_id]), 'label': 'Payment'},
            {'url': reverse('list_cl_returns', args=[c.contractor_id]), 'label': 'CL Returns'},
            {'url': reverse('delete_contractor', args=[c.contractor_id]), 'label': 'Delete', 'css': 'delete'},
        ],
    } for c in contractors]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Contract Labour Act 1970 — Register of Contractors (Form IV)',
        'columns': ['Contractor Name', 'Licence No.', 'Work Description', 'Max Workers', 'Contract End', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_contractor'), 'add_label': 'Add Contractor',
        'empty_message': 'No contractors registered.',
    })


@login_required
def add_contractor(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = ContractorForm(request.POST)
        if form.is_valid():
            con = form.save(commit=False)
            con.company = company
            con.created_by = request.user
            con.save()
            messages.success(request, f"Contractor '{con.contractor_name}' added.")
            return redirect('list_contractors')
    else:
        form = ContractorForm()

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': 'Add Contractor (Form IV)',
        'cancel_url': reverse('list_contractors'),
    })


@login_required
def update_contractor(request, contractor_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    con = get_object_or_404(contractor, contractor_id=contractor_id, company=company)

    if request.method == 'POST':
        form = ContractorForm(request.POST, instance=con)
        if form.is_valid():
            form.save()
            messages.success(request, f"Contractor '{con.contractor_name}' updated.")
            return redirect('list_contractors')
    else:
        form = ContractorForm(instance=con)

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': f'Edit Contractor — {con.contractor_name}',
        'cancel_url': reverse('list_contractors'),
    })


@login_required
def delete_contractor(request, contractor_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    con = get_object_or_404(contractor, contractor_id=contractor_id, company=company)
    if request.method == 'POST':
        con.delete()
        messages.success(request, f"Contractor '{con.contractor_name}' deleted.")
        return redirect('list_contractors')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Delete Contractor',
        'confirm_message': f'Delete contractor <strong>{con.contractor_name}</strong>? '
                            f'All associated workers and payments will also be deleted.',
        'cancel_url': reverse('list_contractors'),
    })


# ── Contractor Worker Views (Form XII) ───────────────────────────────────────

@login_required
def list_contractor_workers(request, contractor_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    con = get_object_or_404(contractor, contractor_id=contractor_id, company=company)
    workers = contractor_worker.objects.filter(contractor=con).select_related('employee')
    rows = [{
        'cells': [w.employee.name, w.employee.employeecode, w.deployment_start,
                  w.deployment_end or '—', w.work_description[:40]],
        'actions': [],
    } for w in workers]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': f'Contract Workers (Form XII) — {con.contractor_name}',
        'columns': ['Name', 'Code', 'Deployed From', 'Deployed To', 'Work Description'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_contractor_worker', args=[contractor_id]), 'add_label': 'Add Worker',
        'extra_links': [
            {'url': reverse('list_employment_cards', args=[contractor_id]), 'label': 'Employment Cards (Form XIII)'},
            {'url': reverse('list_service_certificates', args=[contractor_id]), 'label': 'Service Certs (Form XIV)'},
            {'url': reverse('list_cl_returns', args=[contractor_id]), 'label': 'Half-Yearly Returns'},
        ],
        'empty_message': 'No workers added yet.',
    })


@login_required
def add_contractor_worker(request, contractor_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    con = get_object_or_404(contractor, contractor_id=contractor_id, company=company)

    if request.method == 'POST':
        form = ContractorWorkerForm(request.POST)
        if form.is_valid():
            w = form.save(commit=False)
            w.contractor = con
            w.created_by = request.user
            w.save()
            messages.success(request, f"Worker '{w.employee.name}' added to {con.contractor_name}.")
            return redirect('list_contractor_workers', contractor_id=contractor_id)
    else:
        form = ContractorWorkerForm()
        form.fields['employee'].queryset = employee.objects.filter(CompanyID=company, is_working=True)

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company, 'con': con,
        'page_title': f'Add Worker — {con.contractor_name}',
        'cancel_url': reverse('list_contractor_workers', args=[contractor_id]),
    })


# ── Contractor Payment Views ──────────────────────────────────────────────────

@login_required
def add_contractor_payment(request, contractor_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    con = get_object_or_404(contractor, contractor_id=contractor_id, company=company)

    if request.method == 'POST':
        form = ContractorPaymentForm(request.POST)
        if form.is_valid():
            pmt = form.save(commit=False)
            pmt.contractor = con
            pmt.created_by = request.user
            pmt.save()
            messages.success(request, f'Payment of ₹{pmt.amount} recorded for {con.contractor_name}.')
            return redirect('list_contractors')
    else:
        form = ContractorPaymentForm()

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company, 'con': con,
        'page_title': f'Record Payment — {con.contractor_name}',
        'cancel_url': reverse('list_contractors'),
    })
