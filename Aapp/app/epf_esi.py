"""
EPF & MP Act, 1952 (EPFO) and ESI Act, 1948 (ESIC) — remaining statutory forms.

Already covered elsewhere in the codebase:
    Aapp/app/employee.py  -> uan_number, epf_memberID, esic_number fields on `employee`
    Aapp/app/wages.py     -> epf_deduction, esi_deduction on `wages_record`

This file adds:
    EPF Form 2          -> EpfNomination          (nominee declaration, due within 1 month of joining)
    EPF Form 5 / ECR     -> EpfMonthlyEcr          (monthly Electronic Challan cum Return)
    ESI Form 1A          -> EsiFamilyMember        (family declaration for dependent benefits)
    ESI Form 7           -> EsiContributionReturn  (half-yearly Apr-Sep / Oct-Mar)
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


RELATIONSHIP_CHOICES = [
    ('spouse',    'Spouse'),
    ('son',       'Son'),
    ('daughter',  'Daughter'),
    ('father',    'Father'),
    ('mother',    'Mother'),
    ('brother',   'Brother'),
    ('sister',    'Sister'),
    ('dependent', 'Dependent'),
    ('other',     'Other'),
]

RETURN_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('filed',   'Filed'),
    ('overdue', 'Overdue'),
]

ESI_PERIOD_CHOICES = [
    ('apr_sep', 'April – September'),
    ('oct_mar', 'October – March'),
]


# ── EPF Models ───────────────────────────────────────────────────────────────

class EpfNomination(models.Model):
    """Form 2 (Rule 6) — Nomination & Declaration, due within 1 month of joining."""
    nomination_id           = models.AutoField(primary_key=True)
    company                 = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    employee                = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID',
                                related_name='epf_nominations')

    nominee_name             = models.CharField(max_length=255)
    relationship              = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    date_of_birth              = models.DateField(null=True, blank=True)
    address                     = models.TextField(blank=True)
    share_percent                = models.DecimalField(max_digits=5, decimal_places=2,
                                help_text='Share % — all nominees for an employee must total 100%')
    aadhar_number                 = models.CharField(max_length=12, blank=True)
    bank_account                   = models.CharField(max_length=20, blank=True)
    bank_ifsc                       = models.CharField(max_length=11, blank=True)
    bank_name                        = models.CharField(max_length=255, blank=True)

    is_minor                          = models.BooleanField(default=False)
    guardian_name                      = models.CharField(max_length=255, blank=True)
    guardian_relationship               = models.CharField(max_length=100, blank=True)
    guardian_address                     = models.TextField(blank=True)

    is_eps_nominee                        = models.BooleanField(default=False,
                                help_text='Also nominee for EPS pension (Form 2 Part B)')
    nomination_date                        = models.DateField()
    is_active                               = models.BooleanField(default=True)

    created_by                               = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='epf_nominations_created')
    created_date                              = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'epf_nomination'
        ordering = ['employee', 'nominee_name']

    def __str__(self):
        return f"{self.employee.employeecode} — EPF Nominee: {self.nominee_name} ({self.share_percent}%)"


class EpfMonthlyEcr(models.Model):
    """Monthly Electronic Challan cum Return — due 15th of following month."""
    ecr_id                  = models.AutoField(primary_key=True)
    company                 = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    salary_month             = models.PositiveSmallIntegerField()
    salary_year                = models.PositiveSmallIntegerField()

    total_members                = models.PositiveIntegerField(default=0)
    total_new_joiners              = models.PositiveIntegerField(default=0)
    total_leavers                    = models.PositiveIntegerField(default=0)
    total_epf_wages                   = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    employee_epf                       = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                help_text='Employee EPF @ 12% of basic+DA')
    employer_epf                        = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                help_text='Employer EPF @ 3.67%')
    employer_eps                         = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                help_text='Employer EPS @ 8.33% (capped at ₹15,000 basic)')
    edli_contribution                     = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                help_text='EDLI @ 0.5%')
    admin_charges                          = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                help_text='EPF admin charges @ 0.5% (min ₹500)')
    total_contribution                      = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    challan_no                               = models.CharField(max_length=100, blank=True)
    challan_date                              = models.DateField(null=True, blank=True)
    trrn                                       = models.CharField(max_length=100, blank=True,
                                help_text='Transaction Reference Return Number from EPFO portal')
    filing_status                               = models.CharField(max_length=10, choices=RETURN_STATUS_CHOICES, default='pending')

    created_by                                  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='ecr_created')
    created_date                                 = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'epf_monthly_ecr'
        unique_together  = ('company', 'salary_month', 'salary_year')
        ordering         = ['-salary_year', '-salary_month']

    def save(self, *args, **kwargs):
        self.total_contribution = round(
            float(self.employee_epf) + float(self.employer_epf) +
            float(self.employer_eps) + float(self.edli_contribution) +
            float(self.admin_charges), 2
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"ECR {self.salary_month}/{self.salary_year} — {self.company.company_name}"


# ── ESI Models ───────────────────────────────────────────────────────────────

class EsiFamilyMember(models.Model):
    """Form 1A (Rule 14) — Family Declaration for dependent benefits."""
    member_id                = models.AutoField(primary_key=True)
    company                  = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    employee                 = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID',
                                related_name='esi_family_members')

    member_name                = models.CharField(max_length=255)
    relationship                 = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    date_of_birth                  = models.DateField(null=True, blank=True)
    gender                          = models.CharField(max_length=10,
                                choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')])
    aadhar_number                    = models.CharField(max_length=12, blank=True)
    is_dependent                      = models.BooleanField(default=True)
    is_residing_with                   = models.BooleanField(default=True)

    date_added                          = models.DateField(auto_now_add=True)
    date_removed                         = models.DateField(null=True, blank=True,
                                help_text='Form 1B — change in family (death/marriage/etc.)')
    reason_for_removal                    = models.CharField(max_length=255, blank=True)

    created_by                             = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='esi_family_created')
    created_date                            = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'esi_family_member'
        ordering = ['employee', 'relationship']

    def __str__(self):
        return f"{self.employee.employeecode} — {self.member_name} ({self.get_relationship_display()})"


class EsiContributionReturn(models.Model):
    """Form 7 (Rule 26) — Half-Yearly Return of Contributions (Apr-Sep & Oct-Mar)."""
    return_id                  = models.AutoField(primary_key=True)
    company                    = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    year                         = models.PositiveSmallIntegerField()
    contribution_period            = models.CharField(max_length=10, choices=ESI_PERIOD_CHOICES)

    total_covered_employees          = models.PositiveIntegerField(default=0)
    total_wages                        = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    employer_contribution                = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                help_text='Employer ESI @ 3.25% of wages')
    employee_contribution                  = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                help_text='Employee ESI @ 0.75% of wages')
    total_contribution                       = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    challan_no                                = models.CharField(max_length=100, blank=True)
    challan_date                               = models.DateField(null=True, blank=True)
    filing_status                               = models.CharField(max_length=10, choices=RETURN_STATUS_CHOICES, default='pending')
    filed_date                                   = models.DateField(null=True, blank=True)
    acknowledgement_no                            = models.CharField(max_length=100, blank=True)

    created_by                                     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='esi_returns_created')
    created_date                                    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'esi_contribution_return'
        unique_together  = ('company', 'year', 'contribution_period')
        ordering         = ['-year', '-contribution_period']

    def save(self, *args, **kwargs):
        self.total_contribution = round(
            float(self.employer_contribution) + float(self.employee_contribution), 2
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"ESI Return {self.get_contribution_period_display()} {self.year} — {self.company.company_name}"


# ── Forms ────────────────────────────────────────────────────────────────────

class EpfNominationForm(forms.ModelForm):
    class Meta:
        model = EpfNomination
        fields = ['nominee_name', 'relationship', 'date_of_birth', 'address', 'share_percent',
                  'aadhar_number', 'bank_account', 'bank_ifsc', 'bank_name', 'is_minor',
                  'guardian_name', 'guardian_relationship', 'guardian_address',
                  'is_eps_nominee', 'nomination_date']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'nomination_date': forms.DateInput(attrs={'type': 'date'}),
        }


class EpfMonthlyEcrForm(forms.ModelForm):
    class Meta:
        model = EpfMonthlyEcr
        fields = ['salary_month', 'salary_year', 'total_members', 'total_new_joiners', 'total_leavers',
                  'total_epf_wages', 'employee_epf', 'employer_epf', 'employer_eps',
                  'edli_contribution', 'admin_charges', 'challan_no', 'challan_date', 'trrn', 'filing_status']
        widgets = {'challan_date': forms.DateInput(attrs={'type': 'date'})}


class EsiFamilyMemberForm(forms.ModelForm):
    class Meta:
        model = EsiFamilyMember
        fields = ['member_name', 'relationship', 'date_of_birth', 'gender', 'aadhar_number',
                  'is_dependent', 'is_residing_with']
        widgets = {'date_of_birth': forms.DateInput(attrs={'type': 'date'})}


class EsiContributionReturnForm(forms.ModelForm):
    class Meta:
        model = EsiContributionReturn
        fields = ['year', 'contribution_period', 'total_covered_employees', 'total_wages',
                  'employer_contribution', 'employee_contribution', 'challan_no', 'challan_date',
                  'filing_status', 'filed_date', 'acknowledgement_no']
        widgets = {
            'challan_date': forms.DateInput(attrs={'type': 'date'}),
            'filed_date': forms.DateInput(attrs={'type': 'date'}),
        }


# ── Helper ───────────────────────────────────────────────────────────────────

def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── EPF Nomination Views (Form 2) ────────────────────────────────────────────

@login_required
def list_epf_nominations(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    nominations = EpfNomination.objects.filter(company=company).select_related('employee')
    rows = [{
        'cells': [n.employee.employeecode, n.nominee_name, n.get_relationship_display(),
                  f'{n.share_percent}%', n.nomination_date],
        'actions': [{'url': reverse('delete_epf_nomination', args=[n.nomination_id]), 'label': 'Delete', 'css': 'delete'}],
    } for n in nominations]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'EPF Nomination & Declaration (Form 2)',
        'columns': ['Employee', 'Nominee', 'Relationship', 'Share %', 'Nomination Date'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_epf_nomination'), 'add_label': 'Add Nomination',
        'empty_message': 'No EPF nominations recorded yet.',
    })


@login_required
def add_epf_nomination(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    employees = employee.objects.filter(CompanyID=company, is_working=True).order_by('name')

    if request.method == 'POST':
        emp = get_object_or_404(employee, employeeid=request.POST.get('employee_id'), CompanyID=company)
        form = EpfNominationForm(request.POST)
        if form.is_valid():
            nom = form.save(commit=False)
            nom.company = company
            nom.employee = emp
            nom.created_by = request.user
            nom.save()
            messages.success(request, f'EPF nomination added for {emp.name}.')
            return redirect('list_epf_nominations')
    else:
        form = EpfNominationForm()

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'employees': employees, 'company': company,
        'page_title': 'Add EPF Nomination (Form 2)',
        'cancel_url': reverse('list_epf_nominations'),
    })


@login_required
def delete_epf_nomination(request, nomination_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    nom = get_object_or_404(EpfNomination, nomination_id=nomination_id, company=company)
    if request.method == 'POST':
        nom.delete()
        messages.success(request, 'EPF nomination deleted.')
        return redirect('list_epf_nominations')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Delete EPF Nomination',
        'confirm_message': f'Delete EPF nomination for <strong>{nom.nominee_name}</strong> '
                            f'({nom.employee.name})?',
        'cancel_url': reverse('list_epf_nominations'),
    })


# ── EPF Monthly ECR Views ────────────────────────────────────────────────────

@login_required
def list_epf_ecr(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    records = EpfMonthlyEcr.objects.filter(company=company)
    rows = [{
        'cells': [f'{r.salary_month}/{r.salary_year}', r.total_members, r.total_epf_wages,
                  r.total_contribution, r.trrn or '—', r.get_filing_status_display()],
        'actions': [{'url': reverse('alter_epf_ecr', args=[r.ecr_id]), 'label': 'Edit', 'css': 'edit'}],
    } for r in records]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'EPF Monthly ECR (Electronic Challan cum Return)',
        'columns': ['Month/Year', 'Members', 'EPF Wages', 'Total Contribution', 'TRRN', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_epf_ecr'), 'add_label': 'Add ECR',
        'empty_message': 'No ECR filed yet.',
    })


@login_required
def add_epf_ecr(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = EpfMonthlyEcrForm(request.POST)
        if form.is_valid():
            ecr = form.save(commit=False)
            ecr.company = company
            ecr.created_by = request.user
            ecr.save()
            messages.success(request, 'EPF ECR recorded.')
            return redirect('list_epf_ecr')
    else:
        form = EpfMonthlyEcrForm()

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': 'Add Monthly ECR',
        'cancel_url': reverse('list_epf_ecr'),
    })


@login_required
def alter_epf_ecr(request, ecr_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    ecr = get_object_or_404(EpfMonthlyEcr, ecr_id=ecr_id, company=company)

    if request.method == 'POST':
        form = EpfMonthlyEcrForm(request.POST, instance=ecr)
        if form.is_valid():
            form.save()
            messages.success(request, 'EPF ECR updated.')
            return redirect('list_epf_ecr')
    else:
        form = EpfMonthlyEcrForm(instance=ecr)

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': f'Edit ECR — {ecr.salary_month}/{ecr.salary_year}',
        'cancel_url': reverse('list_epf_ecr'),
    })


# ── ESI Family Member Views (Form 1A) ────────────────────────────────────────

@login_required
def list_esi_family(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    members = EsiFamilyMember.objects.filter(company=company).select_related('employee')
    rows = [{
        'cells': [m.employee.employeecode, m.member_name, m.get_relationship_display(),
                  m.date_of_birth or '—', 'Active' if not m.date_removed else f'Removed {m.date_removed}'],
        'actions': [] if m.date_removed else
                   [{'url': reverse('remove_esi_family', args=[m.member_id]), 'label': 'Remove (Form 1B)'}],
    } for m in members]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'ESI Family Declaration (Form 1A)',
        'columns': ['Employee', 'Member Name', 'Relationship', 'DOB', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_esi_family'), 'add_label': 'Add Family Member',
        'empty_message': 'No family members declared yet.',
    })


@login_required
def add_esi_family(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    employees = employee.objects.filter(CompanyID=company, is_working=True).order_by('name')

    if request.method == 'POST':
        emp = get_object_or_404(employee, employeeid=request.POST.get('employee_id'), CompanyID=company)
        form = EsiFamilyMemberForm(request.POST)
        if form.is_valid():
            member = form.save(commit=False)
            member.company = company
            member.employee = emp
            member.created_by = request.user
            member.save()
            messages.success(request, f'Family member added for {emp.name}.')
            return redirect('list_esi_family')
    else:
        form = EsiFamilyMemberForm()

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'employees': employees, 'company': company,
        'page_title': 'Add Family Member (ESI Form 1A)',
        'cancel_url': reverse('list_esi_family'),
    })


@login_required
def remove_esi_family(request, member_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    member = get_object_or_404(EsiFamilyMember, member_id=member_id, company=company)
    if request.method == 'POST':
        from datetime import date
        member.date_removed = request.POST.get('date_removed') or date.today()
        member.reason_for_removal = request.POST.get('reason_for_removal', '')
        member.save()
        messages.success(request, 'Family member marked as removed (Form 1B).')
        return redirect('list_esi_family')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Remove Family Member (Form 1B)',
        'confirm_message': f'Mark <strong>{member.member_name}</strong> as removed from '
                            f'{member.employee.name}\u2019s family declaration?',
        'extra_fields': [
            {'name': 'date_removed', 'label': 'Date Removed', 'type': 'date'},
            {'name': 'reason_for_removal', 'label': 'Reason', 'type': 'text'},
        ],
        'cancel_url': reverse('list_esi_family'),
    })


# ── ESI Contribution Return Views (Form 7) ───────────────────────────────────

@login_required
def list_esi_returns(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    returns = EsiContributionReturn.objects.filter(company=company)
    rows = [{
        'cells': [r.year, r.get_contribution_period_display(), r.total_covered_employees,
                  r.total_wages, r.total_contribution, r.get_filing_status_display()],
        'actions': [{'url': reverse('alter_esi_return', args=[r.return_id]), 'label': 'Edit', 'css': 'edit'}],
    } for r in returns]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'ESI Half-Yearly Contribution Return (Form 7)',
        'columns': ['Year', 'Period', 'Covered Employees', 'Total Wages', 'Total Contribution', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_esi_return'), 'add_label': 'Add Contribution Return',
        'empty_message': 'No ESI returns filed yet.',
    })


@login_required
def add_esi_return(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = EsiContributionReturnForm(request.POST)
        if form.is_valid():
            ret = form.save(commit=False)
            ret.company = company
            ret.created_by = request.user
            ret.save()
            messages.success(request, 'ESI contribution return recorded.')
            return redirect('list_esi_returns')
    else:
        form = EsiContributionReturnForm()

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': 'Add ESI Contribution Return (Form 7)',
        'cancel_url': reverse('list_esi_returns'),
    })


@login_required
def alter_esi_return(request, return_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    ret = get_object_or_404(EsiContributionReturn, return_id=return_id, company=company)

    if request.method == 'POST':
        form = EsiContributionReturnForm(request.POST, instance=ret)
        if form.is_valid():
            form.save()
            messages.success(request, 'ESI return updated.')
            return redirect('list_esi_returns')
    else:
        form = EsiContributionReturnForm(instance=ret)

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': f'Edit ESI Return — {ret.get_contribution_period_display()} {ret.year}',
        'cancel_url': reverse('list_esi_returns'),
    })
