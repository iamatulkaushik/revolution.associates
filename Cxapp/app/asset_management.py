"""
Cxapp/app/asset_management.py
================================
Asset tracking for the Cxapp portal — mirrors Aapp.app.asset_management
but scoped to CxOwnerProfile/CxEmployee.
"""

from datetime import date
from decimal import Decimal

from django.db import models
from django.forms import ModelForm
from django.forms.widgets import Select, TextInput, NumberInput, DateInput, Textarea

from Cxapp.app.employee import CxEmployee

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


class CxAsset(models.Model):
    asset_id = models.AutoField(primary_key=True)
    company = models.ForeignKey('Cxapp.CxOwnerProfile', on_delete=models.CASCADE, related_name='assets')
    asset_name = models.CharField(max_length=150)
    asset_category = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    purchase_date = models.DateField(null=True, blank=True)
    purchase_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    current_valuation = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=15, choices=ASSET_STATUS_CHOICES, default='available')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_assets'
        ordering = ['asset_name']
        verbose_name = "Asset"

    def __str__(self):
        return f"{self.asset_name} ({self.serial_number or 'no serial'})"


class CxAssetAssignment(models.Model):
    assignment_id = models.AutoField(primary_key=True)
    asset = models.ForeignKey(CxAsset, on_delete=models.CASCADE, related_name='assignments')
    employee = models.ForeignKey(CxEmployee, on_delete=models.CASCADE, related_name='asset_assignments')
    assigned_on = models.DateField(default=date.today)
    returned_on = models.DateField(null=True, blank=True)
    condition_on_return = models.CharField(max_length=255, blank=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_asset_assignment'
        ordering = ['-assigned_on']
        verbose_name = "Asset Assignment"

    def __str__(self):
        return f"{self.asset.asset_name} -> {self.employee.name}"


class CxAssetRecovery(models.Model):
    recovery_id = models.AutoField(primary_key=True)
    asset = models.ForeignKey(CxAsset, on_delete=models.CASCADE, related_name='recoveries')
    employee = models.ForeignKey(CxEmployee, on_delete=models.CASCADE, related_name='asset_recoveries')
    company = models.ForeignKey('Cxapp.CxOwnerProfile', on_delete=models.CASCADE)
    reason = models.CharField(max_length=20, choices=[('damage', 'Damage'), ('theft', 'Theft/Loss')])
    recovery_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=RECOVERY_STATUS_CHOICES, default='pending')
    remarks = models.CharField(max_length=500, blank=True)
    raised_on = models.DateField(default=date.today)
    resolved_on = models.DateField(null=True, blank=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_asset_recovery'
        ordering = ['-raised_on']
        verbose_name = "Asset Recovery"

    def __str__(self):
        return f"Recovery #{self.recovery_id} - {self.asset.asset_name} - {self.employee.name}"


class CxAssetForm(ModelForm):
    class Meta:
        model = CxAsset
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


class CxAssetAssignmentForm(ModelForm):
    class Meta:
        model = CxAssetAssignment
        fields = ['asset', 'employee', 'assigned_on']
        widgets = {
            'asset': Select(attrs={'class': 'form-control'}),
            'employee': Select(attrs={'class': 'form-control'}),
            'assigned_on': DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class CxAssetRecoveryForm(ModelForm):
    class Meta:
        model = CxAssetRecovery
        fields = ['asset', 'employee', 'reason', 'recovery_amount', 'remarks']
        widgets = {
            'asset': Select(attrs={'class': 'form-control'}),
            'employee': Select(attrs={'class': 'form-control'}),
            'reason': Select(attrs={'class': 'form-control'}),
            'recovery_amount': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'remarks': Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


def get_pending_asset_recovery(employee_obj):
    """Used by CxFnFSettlement.compute() to auto-pull pending recoveries."""
    total = CxAssetRecovery.objects.filter(
        employee=employee_obj, status='pending'
    ).aggregate(total=models.Sum('recovery_amount'))['total']
    return total or Decimal('0')


# =====================================================================
# VIEWS
# =====================================================================

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse


def _can_manage_payroll(request):
    if getattr(request, 'cx_sub_user', None) is None:
        return True
    return request.cx_sub_user.get_role_permissions().get('wages', False)


def cxapp_list_assets(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_list_assets)(request)


def _list_assets(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to view assets.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    assets = CxAsset.objects.filter(company=owner_profile).order_by('asset_name')
    return render(request, 'Cxapp/assets/asset_list.html', {'assets': assets})


def cxapp_create_asset(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_create_asset)(request)


def _create_asset(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to manage assets.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    if request.method == 'POST':
        form = CxAssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.company = owner_profile
            asset.save()
            messages.success(request, 'Asset added successfully.')
            return redirect('cxapp_list_assets')
    else:
        form = CxAssetForm()

    return render(request, 'Cxapp/assets/create_asset.html', {'form': form})


def cxapp_assign_asset(request, asset_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_assign_asset)(request, asset_id)


def _assign_asset(request, asset_id):
    owner_profile = request.cx_owner_profile
    asset = get_object_or_404(CxAsset, asset_id=asset_id, company=owner_profile)

    if request.method == 'POST':
        form = CxAssetAssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.asset = asset
            assignment.save()
            asset.status = 'assigned'
            asset.save(update_fields=['status'])
            messages.success(request, 'Asset assigned successfully.')
            return redirect('cxapp_list_assets')
    else:
        form = CxAssetAssignmentForm(initial={'asset': asset})
        form.fields['employee'].queryset = CxEmployee.objects.filter(company=owner_profile, is_working=True)

    return render(request, 'Cxapp/assets/assign_asset.html', {'form': form, 'asset': asset})


def cxapp_list_asset_recoveries(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_list_asset_recoveries)(request)


def _list_asset_recoveries(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to view recoveries.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    recoveries = CxAssetRecovery.objects.filter(company=owner_profile).select_related('asset', 'employee').order_by('-raised_on')
    return render(request, 'Cxapp/assets/recovery_list.html', {'recoveries': recoveries})


def cxapp_create_asset_recovery(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_create_asset_recovery)(request)


def _create_asset_recovery(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to manage recoveries.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    if request.method == 'POST':
        form = CxAssetRecoveryForm(request.POST)
        if form.is_valid():
            recovery = form.save(commit=False)
            recovery.company = owner_profile
            recovery.save()
            recovery.asset.status = 'damaged' if recovery.reason == 'damage' else 'lost'
            recovery.asset.save(update_fields=['status'])
            messages.success(request, 'Recovery raised successfully.')
            return redirect('cxapp_list_asset_recoveries')
    else:
        form = CxAssetRecoveryForm()
        form.fields['asset'].queryset = CxAsset.objects.filter(company=owner_profile)
        form.fields['employee'].queryset = CxEmployee.objects.filter(company=owner_profile, is_working=True)

    return render(request, 'Cxapp/assets/create_recovery.html', {'form': form})
