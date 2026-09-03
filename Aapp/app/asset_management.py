"""
Aapp/app/asset_management.py
===============================
Asset tracking for tools/machines at office/factory, per pt_upgrades.md:
"Assets Management for tools/machines at office/factory", "assets
valvation for theft/damage recovery", "assets schedule, list, quantity
for print and records".

Assets can be assigned to an employee; if damaged/lost, a recovery
amount can be raised against that employee and pulled into payroll
deductions or an FnF settlement (see get_pending_asset_recovery(),
used by Aapp.app.fnf_settlement.FnFSettlement.compute()).
"""

from datetime import date
from decimal import Decimal

from django.db import models
from django.forms import ModelForm
from django.forms.widgets import Select, TextInput, NumberInput, DateInput, Textarea

from Aapp.app.employee import employee as employee_model
from Sapp.app.company import Company


ASSET_STATUS_CHOICES = [
    ('available', 'Available'),
    ('assigned', 'Assigned'),
    ('under_repair', 'Under Repair'),
    ('damaged', 'Damaged'),
    ('lost', 'Lost'),
    ('retired', 'Retired'),
]

RECOVERY_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('recovered', 'Recovered'),
    ('waived', 'Waived'),
]


class Asset(models.Model):
    """One physical asset — tool, machine, laptop, etc."""
    asset_id = models.AutoField(primary_key=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='assets')
    asset_name = models.CharField(max_length=150)
    asset_category = models.CharField(max_length=100, blank=True, help_text="e.g. Tool, Machine, Laptop, Furniture")
    serial_number = models.CharField(max_length=100, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    purchase_date = models.DateField(null=True, blank=True)
    purchase_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    current_valuation = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                             help_text="Depreciated/current value, used as the base for damage/theft recovery")
    status = models.CharField(max_length=15, choices=ASSET_STATUS_CHOICES, default='available')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Aapp'
        db_table = 'aa_assets'
        ordering = ['asset_name']
        verbose_name = "Asset"

    def __str__(self):
        return f"{self.asset_name} ({self.serial_number or 'no serial'})"


class AssetAssignment(models.Model):
    """One row per assign/return event — history of who held an asset and when."""
    assignment_id = models.AutoField(primary_key=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='assignments')
    employee = models.ForeignKey(employee_model, on_delete=models.CASCADE, related_name='asset_assignments')
    assigned_on = models.DateField(default=date.today)
    returned_on = models.DateField(null=True, blank=True)
    condition_on_return = models.CharField(max_length=255, blank=True)

    class Meta:
        app_label = 'Aapp'
        db_table = 'aa_asset_assignment'
        ordering = ['-assigned_on']
        verbose_name = "Asset Assignment"

    def __str__(self):
        return f"{self.asset.asset_name} -> {self.employee.name}"

    @property
    def is_active(self):
        return self.returned_on is None


class AssetRecovery(models.Model):
    """
    A damage/theft/loss recovery raised against an employee for a
    specific asset. recovery_amount defaults to the asset's
    current_valuation but can be adjusted (e.g. partial recovery for
    minor damage).
    """
    recovery_id = models.AutoField(primary_key=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='recoveries')
    employee = models.ForeignKey(employee_model, on_delete=models.CASCADE, related_name='asset_recoveries')
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    reason = models.CharField(max_length=20, choices=[('damage', 'Damage'), ('theft', 'Theft/Loss')])
    recovery_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=RECOVERY_STATUS_CHOICES, default='pending')
    remarks = models.CharField(max_length=500, blank=True)

    raised_on = models.DateField(default=date.today)
    resolved_on = models.DateField(null=True, blank=True)

    class Meta:
        app_label = 'Aapp'
        db_table = 'aa_asset_recovery'
        ordering = ['-raised_on']
        verbose_name = "Asset Recovery"

    def __str__(self):
        return f"Recovery #{self.recovery_id} - {self.asset.asset_name} - {self.employee.name}"


class AssetForm(ModelForm):
    class Meta:
        model = Asset
        fields = ['asset_name', 'asset_category', 'serial_number', 'quantity',
                  'purchase_date', 'purchase_value', 'current_valuation']
        widgets = {
            'asset_name': TextInput(attrs={'class': 'form-control'}),
            'asset_category': TextInput(attrs={'class': 'form-control'}),
            'serial_number': TextInput(attrs={'class': 'form-control'}),
            'quantity': NumberInput(attrs={'class': 'form-control'}),
            'purchase_date': DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purchase_value': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'current_valuation': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class AssetAssignmentForm(ModelForm):
    class Meta:
        model = AssetAssignment
        fields = ['asset', 'employee', 'assigned_on']
        widgets = {
            'asset': Select(attrs={'class': 'form-control'}),
            'employee': Select(attrs={'class': 'form-control'}),
            'assigned_on': DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class AssetReturnForm(ModelForm):
    class Meta:
        model = AssetAssignment
        fields = ['returned_on', 'condition_on_return']
        widgets = {
            'returned_on': DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'condition_on_return': Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class AssetRecoveryForm(ModelForm):
    class Meta:
        model = AssetRecovery
        fields = ['asset', 'employee', 'reason', 'recovery_amount', 'remarks']
        widgets = {
            'asset': Select(attrs={'class': 'form-control'}),
            'employee': Select(attrs={'class': 'form-control'}),
            'reason': Select(attrs={'class': 'form-control'}),
            'recovery_amount': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'remarks': Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


def get_pending_asset_recovery(employee_obj):
    """
    Sum of all 'pending' AssetRecovery amounts for this employee —
    used by FnFSettlement.compute() instead of the old manual-only
    asset_recovery_amount field, and can also be pulled into monthly
    payroll deductions if wired there later.
    """
    total = AssetRecovery.objects.filter(
        employee=employee_obj, status='pending'
    ).aggregate(total=models.Sum('recovery_amount'))['total']
    return total or Decimal('0')


# =====================================================================
# VIEWS
# =====================================================================

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse


def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


@login_required
def list_assets(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    assets = Asset.objects.filter(company=company).order_by('asset_name')
    rows = [{
        'cells': [a.asset_name, a.asset_category, a.serial_number or '-', a.quantity,
                  f"Rs. {a.current_valuation}", a.get_status_display()],
        'actions': [
            {'url': reverse('assign_asset', args=[a.asset_id]), 'label': 'Assign', 'css': 'edit'},
            {'url': reverse('alter_asset', args=[a.asset_id]), 'label': 'Edit', 'css': 'edit'},
        ],
    } for a in assets]

    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Assets',
        'columns': ['Name', 'Category', 'Serial', 'Qty', 'Valuation', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('create_asset'), 'add_label': 'Add Asset',
        'empty_message': 'No assets on record yet.',
    })


@login_required
def create_asset(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        form = AssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.company = company
            asset.save()
            messages.success(request, 'Asset added successfully.')
            return redirect('list_assets')
    else:
        form = AssetForm()

    return render(request, 'Aapp/works/create_asset.html', {'form': form, 'company': company})


@login_required
def alter_asset(request, asset_id):
    company = _company(request)
    asset = get_object_or_404(Asset, asset_id=asset_id, company=company)

    if request.method == 'POST':
        form = AssetForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            messages.success(request, 'Asset updated successfully.')
            return redirect('list_assets')
    else:
        form = AssetForm(instance=asset)

    return render(request, 'Aapp/works/alter_asset.html', {'form': form, 'asset': asset})


@login_required
def assign_asset(request, asset_id):
    company = _company(request)
    asset = get_object_or_404(Asset, asset_id=asset_id, company=company)

    if request.method == 'POST':
        form = AssetAssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.asset = asset
            assignment.save()
            asset.status = 'assigned'
            asset.save(update_fields=['status'])
            messages.success(request, 'Asset assigned successfully.')
            return redirect('list_assets')
    else:
        form = AssetAssignmentForm(initial={'asset': asset})
        form.fields['employee'].queryset = employee_model.objects.filter(CompanyID=company, is_working=True)

    return render(request, 'Aapp/works/assign_asset.html', {'form': form, 'asset': asset, 'company': company})


@login_required
def list_asset_recoveries(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    recoveries = AssetRecovery.objects.filter(company=company).select_related('asset', 'employee').order_by('-raised_on')
    rows = [{
        'cells': [r.asset.asset_name, r.employee.employeecode, r.employee.name,
                  r.get_reason_display(), f"Rs. {r.recovery_amount}", r.get_status_display()],
        'actions': [],
    } for r in recoveries]

    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Asset Recoveries',
        'columns': ['Asset', 'Emp Code', 'Name', 'Reason', 'Amount', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('create_asset_recovery'), 'add_label': 'Raise Recovery',
        'empty_message': 'No recoveries raised yet.',
    })


@login_required
def create_asset_recovery(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        form = AssetRecoveryForm(request.POST)
        if form.is_valid():
            recovery = form.save(commit=False)
            recovery.company = company
            recovery.save()
            recovery.asset.status = recovery.reason  # 'damage' or 'theft' doesn't match ASSET_STATUS_CHOICES exactly
            if recovery.reason == 'damage':
                recovery.asset.status = 'damaged'
            elif recovery.reason == 'theft':
                recovery.asset.status = 'lost'
            recovery.asset.save(update_fields=['status'])
            messages.success(request, 'Recovery raised successfully.')
            return redirect('list_asset_recoveries')
    else:
        form = AssetRecoveryForm()
        form.fields['asset'].queryset = Asset.objects.filter(company=company)
        form.fields['employee'].queryset = employee_model.objects.filter(CompanyID=company, is_working=True)

    return render(request, 'Aapp/works/create_asset_recovery.html', {'form': form, 'company': company})
