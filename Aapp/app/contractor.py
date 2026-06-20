from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
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

def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Contractor Views ──────────────────────────────────────────────────────────

@login_required
def list_contractors(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    contractors = contractor.objects.filter(company=company)
    return render(request, 'Aapp/contractor/list_contractors.html', {
        'contractors': contractors, 'company': company,
    })


@login_required
def add_contractor(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    if request.method == 'POST':
        p = request.POST
        contractor.objects.create(
            company=company,
            principal_employer=p.get('principal_employer', company.company_name),
            contractor_name=p.get('contractor_name'),
            contractor_license_no=p.get('contractor_license_no', ''),
            contractor_address=p.get('contractor_address', ''),
            contractor_mobile=p.get('contractor_mobile', ''),
            contractor_email=p.get('contractor_email', ''),
            contractor_pan=p.get('contractor_pan', ''),
            contractor_gstin=p.get('contractor_gstin', ''),
            work_description=p.get('work_description'),
            contract_start_date=p.get('contract_start_date'),
            contract_end_date=p.get('contract_end_date'),
            contract_amount=p.get('contract_amount', 0),
            payment_schedule=p.get('payment_schedule'),
            reason_for_contract=p.get('reason_for_contract', ''),
            max_contract_workers=p.get('max_contract_workers', 0),
            worksite_address=p.get('worksite_address', ''),
            created_by=request.user,
        )
        messages.success(request, f"Contractor '{p.get('contractor_name')}' added.")
        return redirect('Aapp:list_contractors')

    return render(request, 'Aapp/contractor/add_contractor.html', {
        'payment_schedules': PAYMENT_SCHEDULE_CHOICES, 'company': company,
    })


@login_required
def update_contractor(request, contractor_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    con = get_object_or_404(contractor, contractor_id=contractor_id, company=company)

    if request.method == 'POST':
        p = request.POST
        con.contractor_name       = p.get('contractor_name', con.contractor_name)
        con.contractor_license_no = p.get('contractor_license_no', con.contractor_license_no)
        con.contractor_address    = p.get('contractor_address', con.contractor_address)
        con.contractor_mobile     = p.get('contractor_mobile', con.contractor_mobile)
        con.contractor_email      = p.get('contractor_email', con.contractor_email)
        con.contractor_pan        = p.get('contractor_pan', con.contractor_pan)
        con.contractor_gstin      = p.get('contractor_gstin', con.contractor_gstin)
        con.work_description      = p.get('work_description', con.work_description)
        con.contract_start_date   = p.get('contract_start_date', con.contract_start_date)
        con.contract_end_date     = p.get('contract_end_date', con.contract_end_date)
        con.contract_amount       = p.get('contract_amount', con.contract_amount)
        con.payment_schedule      = p.get('payment_schedule', con.payment_schedule)
        con.reason_for_contract   = p.get('reason_for_contract', con.reason_for_contract)
        con.status                = p.get('status', con.status)
        con.max_contract_workers  = p.get('max_contract_workers', con.max_contract_workers)
        con.worksite_address      = p.get('worksite_address', con.worksite_address)
        con.updated_by            = request.user
        con.save()
        messages.success(request, 'Contractor updated.')
        return redirect('Aapp:list_contractors')

    return render(request, 'Aapp/contractor/update_contractor.html', {
        'con': con,
        'payment_schedules': PAYMENT_SCHEDULE_CHOICES,
        'statuses': CONTRACT_STATUS_CHOICES,
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
        messages.success(request, 'Contractor deleted.')
        return redirect('Aapp:list_contractors')
    return render(request, 'Aapp/contractor/delete_contractor.html', {'con': con})


# ── Contractor Worker Views ───────────────────────────────────────────────────

@login_required
def list_contractor_workers(request, contractor_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    con     = get_object_or_404(contractor, contractor_id=contractor_id, company=company)
    workers = contractor_worker.objects.filter(contractor=con).select_related('employee')
    return render(request, 'Aapp/contractor/list_contractor_workers.html', {
        'con': con, 'workers': workers, 'company': company,
    })


@login_required
def add_contractor_worker(request, contractor_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    con       = get_object_or_404(contractor, contractor_id=contractor_id, company=company)
    employees = employee.objects.filter(
        CompanyID=company, is_working=True,
        employment_type='Contract'
    ).order_by('name')

    if request.method == 'POST':
        p   = request.POST
        emp = get_object_or_404(employee, employeeid=p.get('employee_id'), CompanyID=company)
        contractor_worker.objects.create(
            contractor=con, company=company, employee=emp,
            deployment_start=p.get('deployment_start'),
            deployment_end=p.get('deployment_end') or None,
            work_description=p.get('work_description', ''),
            created_by=request.user,
        )
        messages.success(request, f'{emp.name} added to contractor.')
        return redirect('Aapp:list_contractor_workers', contractor_id=contractor_id)

    return render(request, 'Aapp/contractor/add_contractor_worker.html', {
        'con': con, 'employees': employees, 'company': company,
    })


# ── Payment Views ─────────────────────────────────────────────────────────────

@login_required
def add_contractor_payment(request, contractor_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    con = get_object_or_404(contractor, contractor_id=contractor_id, company=company)

    if request.method == 'POST':
        p = request.POST
        contractor_payment.objects.create(
            contractor=con, company=company,
            salary_month=int(p.get('salary_month', 0)),
            salary_year=int(p.get('salary_year', 0)),
            payment_amount=p.get('payment_amount'),
            payment_date=p.get('payment_date'),
            payment_reference=p.get('payment_reference', ''),
            remarks=p.get('remarks', ''),
            created_by=request.user,
        )
        messages.success(request, 'Payment recorded.')
        return redirect('Aapp:list_contractors')

    return render(request, 'Aapp/contractor/add_contractor_payment.html', {
        'con': con, 'company': company,
    })
