"""
Shops & Commercial Establishments Act.

establishment_details is the establishment/registration record (Form F) —
kept as-is, no overlap with anything else in the codebase.

The old overtime_register model that lived here has been removed: it
duplicated Aapp.app.attandance.MinimumWagesOvertimeRegister (same Form IV
overtime data, just keyed to `employee` directly instead of via
`attendance`). Its one unique field, ot_reason, was absorbed onto
MinimumWagesOvertimeRegister. Use list_overtime_register /
create_overtime_register (Aapp.app.attandance) instead of the old
list_overtime / add_overtime views.
"""

from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from revolution.app.plan_gate import require_feature
from Sapp.app.company import Company


WEEKLY_OFF_CHOICES = [
    ('sunday',      'Sunday'),
    ('monday',      'Monday'),
    ('tuesday',     'Tuesday'),
    ('wednesday',   'Wednesday'),
    ('thursday',    'Thursday'),
    ('friday',      'Friday'),
    ('saturday',    'Saturday'),
]

OT_RATE_CHOICES = [
    ('single',  'Single Rate'),
    ('double',  'Double Rate (Statutory)'),
]


def _parse_date(value):
    """str/date/datetime/None -> date or None."""
    import datetime
    from django.utils.dateparse import parse_date
    if not value:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return parse_date(str(value).strip())


# ── Model ────────────────────────────────────────────────────────────────────

class establishment_details(models.Model):
    """
    Shops & Commercial Establishments Act — Establishment Register.
    One record per company branch/location.
    """
    estab_id            = models.AutoField(primary_key=True)
    company             = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    is_primary          = models.BooleanField(default=False,
                            help_text='Auto-created from the company Shop Act registration. '
                                       'Address mirrors the company address. One per company.')
    establishment_name  = models.CharField(max_length=255,
                            help_text='Name as registered under Shops & Establishments Act')
    registration_number = models.CharField(max_length=50, blank=True,
                            help_text='Shop Act registration number')
    registration_date   = models.DateField(null=True, blank=True)
    renewal_date        = models.DateField(null=True, blank=True)
    renewal_exempt      = models.BooleanField(default=False,
                            help_text='Renewal exempted (Haryana Shops & Establishments Act renewal '
                                       'requirement was withdrawn from 2025 onward).')

    # Working hours
    opening_time        = models.TimeField(help_text='Daily opening time')
    closing_time        = models.TimeField(help_text='Daily closing time')
    daily_work_hours    = models.DecimalField(max_digits=4, decimal_places=2, default=8.0,
                            help_text='Standard working hours per day (max 9 hrs as per Act)')
    weekly_work_hours   = models.DecimalField(max_digits=5, decimal_places=2, default=48.0,
                            help_text='Standard working hours per week (max 48 hrs as per Act)')

    # Off days
    weekly_off_day      = models.CharField(max_length=15, choices=WEEKLY_OFF_CHOICES, default='sunday')
    second_off_day      = models.CharField(max_length=15, choices=WEEKLY_OFF_CHOICES, blank=True,
                            help_text='Second weekly off if applicable')

    # Overtime
    ot_rate_type        = models.CharField(max_length=10, choices=OT_RATE_CHOICES, default='double')
    max_ot_hours_day    = models.DecimalField(max_digits=4, decimal_places=2, default=2.0,
                            help_text='Max overtime hours per day allowed')
    max_ot_hours_week   = models.DecimalField(max_digits=5, decimal_places=2, default=10.0,
                            help_text='Max overtime hours per week allowed')

    address             = models.TextField(blank=True)
    manager_name        = models.CharField(max_length=255, blank=True,
                            help_text='Manager/Occupier name as per registration')
    manager_mobile      = models.CharField(max_length=15, blank=True)

    created_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='estab_created')
    created_date        = models.DateTimeField(auto_now_add=True)
    updated_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='estab_updated')
    updated_date        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'establishment_details'
        unique_together = ('company', 'registration_number')
        ordering        = ['establishment_name']

    def __str__(self):
        return f"{self.establishment_name} — {self.company.company_name}"

    def save(self, *args, **kwargs):
        # Haryana Shops & Establishments Act: renewal requirement was
        # withdrawn for registrations from 2025 onward. Existing
        # pre-2025 registrations still need periodic renewal.
        # Coerce str -> date (statutory record may hand over raw strings).
        for _f in ('registration_date', 'renewal_date'):
            _v = getattr(self, _f)
            if isinstance(_v, str):
                setattr(self, _f, _parse_date(_v))
        if self.registration_date and self.registration_date.year >= 2025:
            self.renewal_exempt = True
            self.renewal_date = None
        super().save(*args, **kwargs)


# ── Form ─────────────────────────────────────────────────────────────────────

from django import forms as _saforms

class EstablishmentForm(_saforms.ModelForm):
    """
    For an ADDITIONAL (non-primary) establishment/branch only. The
    primary establishment is auto-created from company.shop_act when
    the company's statutory record is saved (see the post_save signal
    below) and is never edited through this form — its registration
    number/date/address always mirror the company record.

    A second storefront/office is the rare case where a company holds
    a separate Shop Act certificate for that location: its own
    registration number, date, and address are entered here.
    """
    class Meta:
        model = establishment_details
        fields = ['establishment_name', 'registration_number', 'registration_date',
                  'renewal_date', 'manager_name', 'manager_mobile', 'address',
                  'daily_work_hours', 'weekly_work_hours', 'weekly_off_day',
                  'opening_time', 'closing_time']
        widgets = {
            'registration_date': _saforms.DateInput(attrs={'type': 'date'}),
            'renewal_date': _saforms.DateInput(attrs={'type': 'date'}),
        }


def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Establishment Views (Punjab Shops Act — Form F / G) ──────────────────────

def _ensure_primary_establishment(company):
    """
    Self-heals the primary establishment for a company that already has
    a Shop Act number on file but predates the auto-sync signal (or
    whose statutory record hasn't been re-saved since). Safe to call on
    every page load — get_or_create is a no-op if it already exists.
    """
    from Sapp.app.company import company_statury
    statutory = company_statury.objects.filter(company=company).first()
    if statutory and statutory.shop_act:
        _sync_primary_establishment(sender=None, instance=statutory)


@login_required
@require_feature("shops_estab")
def list_establishments(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')
    _ensure_primary_establishment(company)
    estabs = establishment_details.objects.filter(company=company).order_by('-is_primary', 'establishment_name')
    rows = [{
        'cells': [e.registration_number or '—',
                  f'{e.establishment_name} (Primary)' if e.is_primary else e.establishment_name,
                  e.manager_name or '—', e.registration_date,
                  'Exempt (2025+)' if e.renewal_exempt else (e.renewal_date or '—')],
        'actions': [
            {'url': reverse('update_establishment', args=[e.estab_id]), 'label': 'Edit', 'css': 'edit'},
            {'url': reverse('download_establishment_cert', args=[e.estab_id]), 'label': 'Certificate PDF', 'css': 'download'},
        ] + ([] if e.is_primary else
             [{'url': reverse('delete_establishment', args=[e.estab_id]), 'label': 'Delete', 'css': 'delete'}]),
    } for e in estabs]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Punjab Shops & Establishments Act 1958 (Haryana) — Establishments (Form F)',
        'columns': ['Reg. No.', 'Establishment', 'Manager', 'Reg. Date', 'Renewal'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_establishment'), 'add_label': 'Register Additional Establishment',
        'extra_links': [{'url': reverse('list_overtime_register'), 'label': 'Overtime Register (Form IV)'}],
        'empty_message': 'No Shop Act registration on file yet — add one under Company Settings.',
    })


@login_required
def add_establishment(request):
    """
    Registers an ADDITIONAL establishment/branch — the rare case where
    a company holds a second storefront or office with its own Shop
    Act certificate. The primary establishment (mirroring the company's
    Shop Act registration and address) already exists automatically;
    this is never used to create it.
    """
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    _ensure_primary_establishment(company)
    if not establishment_details.objects.filter(company=company, is_primary=True).exists():
        messages.error(request, 'No primary Shop Act registration on file for this company. '
                                  'Add the Shop Act number under Company Settings first.')
        return redirect('list_establishments')

    if request.method == 'POST':
        form = EstablishmentForm(request.POST)
        if form.is_valid():
            est = form.save(commit=False)
            est.company = company
            est.is_primary = False
            est.created_by = request.user
            est.save()
            messages.success(request, 'Additional establishment registered.')
            return redirect('list_establishments')
    else:
        form = EstablishmentForm()

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': 'Register Additional Establishment (separate Shop Act certificate)',
        'cancel_url': reverse('list_establishments'),
    })


@login_required
def update_establishment(request, estab_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    est = get_object_or_404(establishment_details, estab_id=estab_id, company=company)

    if est.is_primary:
        # Primary establishment's registration/address always mirror the
        # company statutory record — only operational fields (hours,
        # manager, off-days) are editable here.
        class PrimaryEstablishmentForm(_saforms.ModelForm):
            class Meta:
                model = establishment_details
                fields = ['manager_name', 'manager_mobile', 'daily_work_hours',
                          'weekly_work_hours', 'weekly_off_day', 'opening_time', 'closing_time']
        form_class = PrimaryEstablishmentForm
    else:
        form_class = EstablishmentForm

    if request.method == 'POST':
        form = form_class(request.POST, instance=est)
        if form.is_valid():
            form.save()
            messages.success(request, 'Establishment updated.')
            return redirect('list_establishments')
    else:
        form = form_class(instance=est)

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': f'Edit Establishment — {est.establishment_name}',
        'cancel_url': reverse('list_establishments'),
        'readonly_summary': [
            ('Shop Act Registration No.', est.registration_number or '—'),
            ('Shop Act Registration Date', est.registration_date or '—'),
            ('Address', est.address or '—'),
            ('Renewal', 'Exempt (2025+ registration)' if est.renewal_exempt else (est.renewal_date or 'Not set')),
        ] if est.is_primary else [
            ('Renewal', 'Exempt (2025+ registration)' if est.renewal_exempt else None),
        ],
    })


@login_required
def delete_establishment(request, estab_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    est = get_object_or_404(establishment_details, estab_id=estab_id, company=company)
    if est.is_primary:
        messages.error(request, 'The primary establishment cannot be deleted — it is tied to the '
                                  'company Shop Act registration. Update the registration under '
                                  'Company Settings instead.')
        return redirect('list_establishments')

    if request.method == 'POST':
        est.delete()
        messages.success(request, 'Establishment deleted.')
        return redirect('list_establishments')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Delete Establishment',
        'confirm_message': f'Delete establishment <strong>{est.establishment_name} ({est.registration_number})</strong>?',
        'cancel_url': reverse('list_establishments'),
    })


# ── Auto-sync primary establishment from company Shop Act registration ──────

from django.db.models.signals import post_save


def _sync_primary_establishment(sender, instance, **kwargs):
    """
    Module-level signal receiver (never nested — see engineering
    principles). Connected explicitly below to company_statury's
    post_save rather than via the sender= kwarg here, since
    company_statury lives in Sapp and importing it at module load
    time risks a circular import with Aapp.

    Whenever a company's Shop Act number/date changes, the primary
    establishment (address = company address) is created or updated
    to match — so Form F never drifts from the statutory record.
    """
    if not instance.shop_act:
        return
    company = instance.company
    est, created = establishment_details.objects.get_or_create(
        company=company, is_primary=True,
        defaults={
            'establishment_name': company.company_name,
            'registration_number': instance.shop_act,
            'registration_date': _parse_date(instance.shop_act_date),
            'address': company.full_address,
            'opening_time': '09:00',
            'closing_time': '18:00',
        }
    )
    if not created:
        est.registration_number = instance.shop_act
        est.registration_date = _parse_date(instance.shop_act_date)
        est.address = company.full_address
        est.establishment_name = company.company_name
        est.save()


def connect_primary_establishment_signal():
    """Call once from Aapp's AppConfig.ready() to wire the receiver
    without importing company_statury at module load time."""
    from Sapp.app.company import company_statury
    post_save.connect(_sync_primary_establishment, sender=company_statury,
                       dispatch_uid='sync_primary_establishment')