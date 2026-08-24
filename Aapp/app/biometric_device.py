"""
Aapp/app/biometric_device.py
===============================
Device registration and employee-to-device-ID mapping for
biometric/RFID attendance sync, per pt_upgrades.md:
"Biometric/RFID device mapping and api".

Architecture: a local daemon runs near the physical device (on-prem,
same LAN), reads punches off the device SDK/API, and pushes them to
Aapp/app/punch_log.py's ingest endpoint over HTTPS. This module only
handles device registration and the employee<->device-user-ID mapping
the daemon needs to resolve punches to employees; it does not talk to
hardware directly (no live network access to physical devices from
this server, hence the daemon-relay design instead of Claude/server
polling the device itself).
"""

from django.db import models
from django.forms import ModelForm
from django.forms.widgets import Select, TextInput

from Aapp.app.employee import employee as employee_model
from Sapp.app.company import Company


DEVICE_TYPE_CHOICES = [
    ('biometric', 'Biometric (Fingerprint/Face)'),
    ('rfid', 'RFID Card Reader'),
]


class BiometricDevice(models.Model):
    """One physical device (per branch/gate) registered against a company."""
    device_id = models.AutoField(primary_key=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='biometric_devices')
    device_name = models.CharField(max_length=100, help_text="e.g. 'Main Gate', 'Factory Floor 2'")
    device_type = models.CharField(max_length=10, choices=DEVICE_TYPE_CHOICES)
    device_serial = models.CharField(max_length=100, unique=True, help_text="Manufacturer serial/MAC, used by the daemon to identify itself")
    daemon_api_key = models.CharField(max_length=64, unique=True, help_text="Shared secret the on-prem daemon sends with each push")
    is_active = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'Aapp'
        db_table = 'aa_biometric_devices'
        verbose_name = "Biometric/RFID Device"

    def __str__(self):
        return f"{self.device_name} ({self.get_device_type_display()}) - {self.company.company_name}"


class EmployeeDeviceMapping(models.Model):
    """
    Maps an employee to their device-side user ID (biometric enrollment
    ID or RFID card number) — punches arrive tagged with this ID, not
    the employee's internal employeecode, so this table resolves them.
    """
    mapping_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(employee_model, on_delete=models.CASCADE, related_name='device_mappings')
    device = models.ForeignKey(BiometricDevice, on_delete=models.CASCADE, related_name='employee_mappings')
    device_user_id = models.CharField(max_length=50, help_text="Employee's ID/card number as enrolled on this device")
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'Aapp'
        db_table = 'aa_employee_device_mapping'
        unique_together = ('device', 'device_user_id')
        verbose_name = "Employee Device Mapping"

    def __str__(self):
        return f"{self.employee.name} -> {self.device.device_name} (ID: {self.device_user_id})"


class BiometricDeviceForm(ModelForm):
    class Meta:
        model = BiometricDevice
        fields = ['device_name', 'device_type', 'device_serial']
        widgets = {
            'device_name': TextInput(attrs={'class': 'form-control'}),
            'device_type': Select(attrs={'class': 'form-control'}),
            'device_serial': TextInput(attrs={'class': 'form-control'}),
        }


class EmployeeDeviceMappingForm(ModelForm):
    class Meta:
        model = EmployeeDeviceMapping
        fields = ['employee', 'device', 'device_user_id']
        widgets = {
            'employee': Select(attrs={'class': 'form-control'}),
            'device': Select(attrs={'class': 'form-control'}),
            'device_user_id': TextInput(attrs={'class': 'form-control'}),
        }


def resolve_employee(device, device_user_id):
    """Used by the punch ingest endpoint to map an incoming punch to an employee."""
    mapping = EmployeeDeviceMapping.objects.filter(
        device=device, device_user_id=device_user_id, is_active=True
    ).select_related('employee').first()
    return mapping.employee if mapping else None


def generate_api_key():
    import secrets
    return secrets.token_hex(32)


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
def list_biometric_devices(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    devices = BiometricDevice.objects.filter(company=company).order_by('device_name')
    rows = [{
        'cells': [d.device_name, d.get_device_type_display(), d.device_serial,
                  'Active' if d.is_active else 'Inactive',
                  d.last_sync_at.strftime('%d-%m-%Y %H:%M') if d.last_sync_at else 'Never'],
        'actions': [{'url': reverse('list_device_mappings', args=[d.device_id]), 'label': 'Map Employees', 'css': 'edit'}],
    } for d in devices]

    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Biometric/RFID Devices',
        'columns': ['Device Name', 'Type', 'Serial', 'Status', 'Last Sync'],
        'rows': rows, 'company': company,
        'add_url': reverse('create_biometric_device'), 'add_label': 'Register Device',
        'empty_message': 'No devices registered yet.',
    })


@login_required
def create_biometric_device(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        form = BiometricDeviceForm(request.POST)
        if form.is_valid():
            device = form.save(commit=False)
            device.company = company
            device.daemon_api_key = generate_api_key()
            device.save()
            messages.success(
                request,
                f'Device registered. Daemon API key (copy now, shown once): {device.daemon_api_key}'
            )
            return redirect('list_biometric_devices')
    else:
        form = BiometricDeviceForm()

    return render(request, 'Aapp/works/create_device.html', {'form': form, 'company': company})


@login_required
def list_device_mappings(request, device_id):
    company = _company(request)
    device = get_object_or_404(BiometricDevice, device_id=device_id, company=company)
    mappings = EmployeeDeviceMapping.objects.filter(device=device).select_related('employee')

    rows = [{
        'cells': [m.employee.employeecode, m.employee.name, m.device_user_id,
                  'Active' if m.is_active else 'Inactive'],
        'actions': [],
    } for m in mappings]

    return render(request, 'Aapp/generic/list.html', {
        'page_title': f'Employee Mappings — {device.device_name}',
        'columns': ['Emp Code', 'Name', 'Device User ID', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('create_device_mapping', args=[device_id]), 'add_label': 'Map Employee',
        'empty_message': 'No employees mapped to this device yet.',
    })


@login_required
def create_device_mapping(request, device_id):
    company = _company(request)
    device = get_object_or_404(BiometricDevice, device_id=device_id, company=company)

    if request.method == 'POST':
        form = EmployeeDeviceMappingForm(request.POST)
        if form.is_valid():
            mapping = form.save(commit=False)
            mapping.device = device
            mapping.save()
            messages.success(request, 'Employee mapped to device successfully.')
            return redirect('list_device_mappings', device_id=device_id)
    else:
        form = EmployeeDeviceMappingForm(initial={'device': device})
        form.fields['employee'].queryset = employee_model.objects.filter(CompanyID=company, is_working=True)
        form.fields['device'].queryset = BiometricDevice.objects.filter(company=company)

    return render(request, 'Aapp/works/create_device_mapping.html', {
        'form': form, 'device': device, 'company': company
    })
