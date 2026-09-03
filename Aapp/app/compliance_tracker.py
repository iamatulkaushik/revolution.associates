"""
Centralised statutory compliance calendar.

Tracks due dates and filing status for ALL statutory returns across every
applicable act, for a single company-wide compliance dashboard.

This does not replace the act-specific records (FactoryAnnualReturn,
EsiContributionReturn, etc.) — it's a lightweight summary index so the
dashboard can show "what's due, what's overdue" in one query instead of
hitting a dozen tables.
"""

from django import forms
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from Sapp.app.company import Company


FREQUENCY_CHOICES = [
    ('monthly', 'Monthly'),
    ('bi_monthly', 'Bi-Monthly'),
    ('quarterly', 'Quarterly'),
    ('half_yearly', 'Half-Yearly'),
    ('annual', 'Annual'),
    ('one_time', 'One-Time'),
]

RETURN_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('filed', 'Filed'),
    ('overdue', 'Overdue'),
]


# ── Model ────────────────────────────────────────────────────────────────────

class StatutoryReturnTracker(models.Model):
    tracker_id = models.AutoField(primary_key=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')

    act_name = models.CharField(max_length=255, help_text='e.g. Factories Act 1948, ESI Act 1948')
    form_number = models.CharField(max_length=50, help_text='e.g. Form 34, Form 7, ECR, Form D')
    return_description = models.CharField(max_length=255, help_text='e.g. Annual Return, Half-Yearly Return')
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    due_date = models.DateField()
    period_covered = models.CharField(max_length=50, blank=True, help_text='e.g. Apr 2025 – Sep 2025')

    filing_status = models.CharField(max_length=10, choices=RETURN_STATUS_CHOICES, default='pending')
    filed_date = models.DateField(null=True, blank=True)
    acknowledgement_no = models.CharField(max_length=100, blank=True)
    penalty_if_late = models.CharField(max_length=255, blank=True,
                        help_text='Penalty/fine for late filing per the Act')
    remarks = models.CharField(max_length=500, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='return_tracker_created')
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'statutory_return_tracker'
        ordering = ['due_date']

    def __str__(self):
        return f"{self.act_name} — {self.form_number} — Due {self.due_date}"

    @property
    def is_overdue(self):
        return self.filing_status == 'pending' and self.due_date < timezone.now().date()


# Standard recurring compliance items for Haryana — used to auto-seed a new company's calendar.
STANDARD_COMPLIANCE_CALENDAR = [
    # (act_name, form_number, description, frequency, day, month_or_none)
    ('EPF & MP Act 1952', 'ECR', 'Monthly Electronic Challan cum Return', 'monthly', 15, None),
    ('ESI Act 1948', 'Form 7', 'Half-Yearly Contribution Return (Apr-Sep)', 'half_yearly', 11, 11),
    ('ESI Act 1948', 'Form 7', 'Half-Yearly Contribution Return (Oct-Mar)', 'half_yearly', 12, 5),
    ('Contract Labour Act 1970', 'Form 20(CL)', 'Half-Yearly Return (Jan-Jun)', 'half_yearly', 30, 7),
    ('Contract Labour Act 1970', 'Form 20(CL)', 'Half-Yearly Return (Jul-Dec)', 'half_yearly', 30, 1),
    ('Punjab Labour Welfare Fund Act 1965', 'LWF Challan', 'Bi-Annual Contribution (Jan-Jun)', 'half_yearly', 31, 7),
    ('Punjab Labour Welfare Fund Act 1965', 'LWF Challan', 'Bi-Annual Contribution (Jul-Dec)', 'half_yearly', 31, 1),
    ('Factories Act 1948', 'Form 34', 'Annual Return', 'annual', 31, 1),
    ('Minimum Wages Act 1948', 'Form V', 'Annual Return', 'annual', 1, 2),
    ('Payment of Wages Act 1936', 'Form IV', 'Annual Return', 'annual', 15, 2),
    ('Payment of Bonus Act 1965', 'Form D', 'Annual Return', 'annual', 1, 2),
]


def seed_pt_compliance_item(company, state, year):
    """
    PT return frequency and form vary by state — unlike
    STANDARD_COMPLIANCE_CALENDAR (Haryana-fixed), so this is a separate
    opt-in helper called once a company's PT state is known, not part
    of the fixed seed list. Monthly PT challan is the common pattern
    across most PT-levying states; call once per company per year.
    Idempotent via get_or_create on (company, act_name, period_covered).
    """
    from datetime import date
    import calendar as _cal

    created = 0
    for month in range(1, 13):
        last_day = _cal.monthrange(year, month)[1]
        _, was_created = StatutoryReturnTracker.objects.get_or_create(
            company=company,
            act_name=f"{state.name.title()} Professional Tax Act",
            form_number='PT Challan',
            period_covered=f"{_cal.month_abbr[month]} {year}",
            defaults={
                'return_description': 'Monthly Professional Tax Payment',
                'frequency': 'monthly',
                'due_date': date(year, month, min(last_day, 20)),
            },
        )
        if was_created:
            created += 1
    return created


# ── Form ─────────────────────────────────────────────────────────────────────

class StatutoryReturnTrackerForm(forms.ModelForm):
    class Meta:
        model = StatutoryReturnTracker
        fields = ['act_name', 'form_number', 'return_description', 'frequency', 'due_date',
                  'period_covered', 'filing_status', 'filed_date', 'acknowledgement_no',
                  'penalty_if_late', 'remarks']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'filed_date': forms.DateInput(attrs={'type': 'date'}),
        }


# ── Helper ───────────────────────────────────────────────────────────────────

def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Views ────────────────────────────────────────────────────────────────────

@login_required
def compliance_dashboard(request):
    """Overview of all pending/overdue/filed returns for the selected company."""
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    today = timezone.now().date()
    all_items = StatutoryReturnTracker.objects.filter(company=company)
    overdue = all_items.filter(filing_status='pending', due_date__lt=today)
    upcoming = all_items.filter(filing_status='pending', due_date__gte=today).order_by('due_date')[:10]
    filed = all_items.filter(filing_status='filed').order_by('-filed_date')[:10]

    return render(request, 'Aapp/compliance/dashboard.html', {
        'company': company,
        'overdue': overdue,
        'upcoming': upcoming,
        'filed': filed,
        'overdue_count': overdue.count(),
        'pending_count': all_items.filter(filing_status='pending').count(),
        'total_count': all_items.count(),
    })


@login_required
def list_compliance_items(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')
    items = StatutoryReturnTracker.objects.filter(company=company)
    rows = [{
        'cells': [i.act_name, i.form_number, i.return_description, i.get_frequency_display(),
                  i.due_date, i.get_filing_status_display()],
        'actions': [
            {'url': reverse('alter_compliance_item', args=[i.tracker_id]), 'label': 'Edit', 'css': 'edit'},
        ] + ([{'url': reverse('mark_compliance_filed', args=[i.tracker_id]), 'label': 'Mark Filed'}]
             if i.filing_status != 'filed' else []),
    } for i in items]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Statutory Compliance Calendar — All Acts',
        'columns': ['Act', 'Form No.', 'Description', 'Frequency', 'Due Date', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_compliance_item'), 'add_label': 'Add Compliance Item',
        'extra_links': [
            {'url': reverse('compliance_dashboard'), 'label': 'Back to Dashboard'},
            {'url': reverse('seed_compliance_calendar'), 'label': 'Seed Standard Calendar'},
        ],
        'empty_message': 'No compliance items tracked yet. Use "Seed Standard Calendar" to auto-fill the year.',
    })


@login_required
def add_compliance_item(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        form = StatutoryReturnTrackerForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.company = company
            item.created_by = request.user
            item.save()
            messages.success(request, 'Compliance item added.')
            return redirect('list_compliance_items')
    else:
        form = StatutoryReturnTrackerForm()

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': 'Add Compliance Item',
        'cancel_url': reverse('list_compliance_items'),
    })


@login_required
def alter_compliance_item(request, tracker_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    item = get_object_or_404(StatutoryReturnTracker, tracker_id=tracker_id, company=company)

    if request.method == 'POST':
        form = StatutoryReturnTrackerForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Compliance item updated.')
            return redirect('list_compliance_items')
    else:
        form = StatutoryReturnTrackerForm(instance=item)

    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'company': company,
        'page_title': f'Edit — {item.act_name} {item.form_number}',
        'cancel_url': reverse('list_compliance_items'),
    })


@login_required
def mark_compliance_filed(request, tracker_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    item = get_object_or_404(StatutoryReturnTracker, tracker_id=tracker_id, company=company)
    if request.method == 'POST':
        from datetime import date
        item.filing_status = 'filed'
        item.filed_date = request.POST.get('filed_date') or date.today()
        item.acknowledgement_no = request.POST.get('acknowledgement_no', item.acknowledgement_no)
        item.save()
        messages.success(request, f'{item.form_number} marked as filed.')
        return redirect('list_compliance_items')
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Mark as Filed',
        'confirm_message': f'Mark <strong>{item.act_name} — {item.form_number}</strong> '
                            f'({item.return_description}) as filed?',
        'extra_fields': [
            {'name': 'filed_date', 'label': 'Filed Date', 'type': 'date'},
            {'name': 'acknowledgement_no', 'label': 'Acknowledgement No.', 'type': 'text'},
        ],
        'cancel_url': reverse('list_compliance_items'),
    })


@login_required
def seed_compliance_calendar(request):
    """One-click seed of the standard Haryana compliance calendar for the current year."""
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        from datetime import date
        year = int(request.POST.get('year', date.today().year))
        created_count = 0
        for act_name, form_number, desc, freq, day, month in STANDARD_COMPLIANCE_CALENDAR:
            due_year = year + 1 if (month and month <= 2 and freq != 'monthly') else year
            try:
                due = date(due_year, month or 1, day)
            except ValueError:
                continue
            _, created = StatutoryReturnTracker.objects.get_or_create(
                company=company, act_name=act_name, form_number=form_number,
                return_description=desc, due_date=due,
                defaults={'frequency': freq, 'created_by': request.user},
            )
            if created:
                created_count += 1
        messages.success(request, f'Seeded {created_count} compliance items for {year}.')
        return redirect('list_compliance_items')

    from datetime import date
    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Seed Standard Compliance Calendar',
        'confirm_message': 'This will auto-fill the standard Haryana statutory compliance calendar '
                            '(EPF ECR, ESI returns, Contract Labour returns, LWF, Factory annual return, '
                            'Minimum Wages, Payment of Wages, Bonus annual return) for the selected year. '
                            'Existing matching entries are skipped.',
        'extra_fields': [{'name': 'year', 'label': 'Year', 'type': 'text', 'value': date.today().year}],
        'submit_label': 'Seed Calendar',
        'cancel_url': reverse('list_compliance_items'),
    })
