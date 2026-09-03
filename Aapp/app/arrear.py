"""
Aapp/app/arrear.py
====================
Employee Arrear — per pt_upgrades.md: "two different files, Arrear |
Increment", "if deductions in arrear, compliances of epf, labour, i.tax
etc saprate schedule". This is the Arrear half.

An Arrear record covers the shortfall between what was actually paid
in an already-processed month (from salary_slip) and what should have
been paid had a new/increased basic+HRA been in effect. It also
recomputes the statutory deductions (PF/labour/PT/IT) on that shortfall
separately, since those liabilities change too when back-pay is added —
this recompute is kept in its own schedule, not merged into the salary
shortfall schedule, per spec.

Arrears can originate from an Increment (linked via increment FK) or be
entered standalone (increment=None) for other backdated pay corrections.
"""

from decimal import Decimal

from django.db import models
from django.forms import ModelForm
from django.forms.widgets import Select, NumberInput, Textarea

from Aapp.app.employee import employee as employee_model
from Sapp.app.company import Company


class Arrear(models.Model):
    """One row per employee per arrear-affected month."""
    arrear_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(employee_model, on_delete=models.CASCADE, related_name='arrears')
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    increment = models.ForeignKey('Aapp.Increment', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='arrears')

    arrear_month = models.PositiveSmallIntegerField(help_text="The already-processed month this arrear covers")
    arrear_year = models.PositiveIntegerField()

    old_basic_paid = models.DecimalField(max_digits=10, decimal_places=2)
    old_hra_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    revised_basic = models.DecimalField(max_digits=10, decimal_places=2)
    revised_hra = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    gross_shortfall = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                           help_text="Auto-computed: revised - old paid")

    # Statutory recompute on the shortfall (kept separate per spec)
    pf_recompute = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    labour_recompute = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pt_recompute = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    income_tax_recompute = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    net_arrear_payable = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                              help_text="gross_shortfall minus statutory recompute total")

    payout_month = models.PositiveSmallIntegerField(help_text="Month this arrear will actually be paid out in")
    payout_year = models.PositiveIntegerField()

    is_paid = models.BooleanField(default=False)
    remarks = models.CharField(max_length=500, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        app_label = 'Aapp'
        db_table = 'aa_arrears'
        ordering = ['-arrear_year', '-arrear_month']
        verbose_name = "Employee Arrear"

    def __str__(self):
        return f"Arrear #{self.arrear_id} - {self.employee.name} - {self.arrear_month}/{self.arrear_year}"

    def compute(self):
        """
        Recomputes gross_shortfall and statutory recompute fields from
        the stored old/revised basic+HRA, and the original salary_slip
        for that month (to get the actual gates/rates that applied then).
        Does not save — caller calls .save() after.
        """
        from Aapp.app.salary_processing import salary_slip
        from Aapp.app.statutory_gates import get_company_gates
        from Sapp.app.professional_tax import get_pt_amount
        from Aapp.app.income_tax import EmployeeTaxProfile, calculate_monthly_tds, current_financial_year
        from datetime import date

        old_slip = salary_slip.objects.filter(
            employee_id=self.employee, processing_id__month=self.arrear_month,
            processing_id__year=self.arrear_year
        ).select_related('designation_id').first()

        old_gross = self.old_basic_paid + self.old_hra_paid
        new_gross = self.revised_basic + self.revised_hra
        self.gross_shortfall = new_gross - old_gross

        gates = get_company_gates(self.company)
        desig = old_slip.designation_id if old_slip else None

        # PF recompute on the shortfall (fail-closed exactly like the live engine)
        pf_applicable = gates['epf'] and bool(getattr(self.employee, 'uan_number', ''))
        if pf_applicable and desig:
            ed_rate = Decimal(str(desig.ed_epf_per)) / Decimal('100')
            self.pf_recompute = (self.gross_shortfall * ed_rate).quantize(Decimal('0.01'))
        else:
            self.pf_recompute = Decimal('0')

        # Labour Welfare recompute
        if gates['labour'] and desig:
            lw_rate = Decimal(str(desig.ed_labourwelfare_per)) / Decimal('100')
            self.labour_recompute = (self.gross_shortfall * lw_rate).quantize(Decimal('0.01'))
        else:
            self.labour_recompute = Decimal('0')

        # PT recompute — re-checks slab against the NEW effective gross for that month
        state_obj = self.employee.perm_state or self.employee.temp_state
        if gates['pt'] and state_obj:
            new_pt = Decimal(str(get_pt_amount(state_obj, new_gross)))
            old_pt = old_slip.professional_tax if old_slip else Decimal('0')
            self.pt_recompute = max(Decimal('0'), new_pt - old_pt)
        else:
            self.pt_recompute = Decimal('0')

        # Income tax recompute — treat shortfall as extra income in the payout month's FY
        if gates['income_tax'] and getattr(self.employee, 'pan_number', None):
            fy = current_financial_year(date(self.payout_year, self.payout_month, 1))
            tax_profile = EmployeeTaxProfile.objects.filter(employee=self.employee, financial_year=fy).first()
            months_remaining = (12 - (self.payout_month - 4)) if self.payout_month >= 4 else (12 - (self.payout_month + 8))
            self.income_tax_recompute = calculate_monthly_tds(
                self.employee, self.gross_shortfall * Decimal('12'), tax_profile, max(months_remaining, 1)
            )
        else:
            self.income_tax_recompute = Decimal('0')

        total_recompute = (
            self.pf_recompute + self.labour_recompute + self.pt_recompute + self.income_tax_recompute
        )
        self.net_arrear_payable = self.gross_shortfall - total_recompute


class ArrearForm(ModelForm):
    class Meta:
        model = Arrear
        fields = ['employee', 'increment', 'arrear_month', 'arrear_year',
                  'old_basic_paid', 'old_hra_paid', 'revised_basic', 'revised_hra',
                  'payout_month', 'payout_year', 'remarks']
        widgets = {
            'employee': Select(attrs={'class': 'form-control'}),
            'increment': Select(attrs={'class': 'form-control'}),
            'arrear_month': NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12}),
            'arrear_year': NumberInput(attrs={'class': 'form-control'}),
            'old_basic_paid': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'old_hra_paid': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'revised_basic': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'revised_hra': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'payout_month': NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12}),
            'payout_year': NumberInput(attrs={'class': 'form-control'}),
            'remarks': Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


def generate_arrears_for_increment(increment_obj, from_month, from_year, to_month, to_year, payout_month, payout_year):
    """
    Bulk-generates one Arrear row per month in the given range for a
    single increment — used when an increment is backdated across
    multiple already-processed months. Skips months with no existing
    salary_slip (nothing was paid yet, so no shortfall to correct).
    Returns the list of created Arrear instances (unsaved compute()
    already applied, saved before return).
    """
    from Aapp.app.salary_processing import salary_slip

    created = []
    y, m = from_year, from_month
    while (y, m) <= (to_year, to_month):
        slip = salary_slip.objects.filter(
            employee_id=increment_obj.employee, processing_id__month=m, processing_id__year=y
        ).first()
        if slip:
            arrear = Arrear(
                employee=increment_obj.employee,
                company=increment_obj.company,
                increment=increment_obj,
                arrear_month=m,
                arrear_year=y,
                old_basic_paid=slip.basic_earned,
                old_hra_paid=slip.hra_earned,
                revised_basic=increment_obj.new_basicpay,
                revised_hra=increment_obj.new_hra,
                payout_month=payout_month,
                payout_year=payout_year,
            )
            arrear.compute()
            arrear.save()
            created.append(arrear)
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return created


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
def list_arrears(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    arrears = Arrear.objects.filter(company=company).select_related('employee').order_by(
        '-arrear_year', '-arrear_month'
    )
    rows = [{
        'cells': [
            a.arrear_id, a.employee.employeecode, a.employee.name,
            f"{a.arrear_month}/{a.arrear_year}", f"Rs. {a.gross_shortfall}",
            f"Rs. {a.net_arrear_payable}", f"{a.payout_month}/{a.payout_year}",
            'Paid' if a.is_paid else 'Pending',
        ],
        'actions': [
            {'url': reverse('view_arrear_schedule', args=[a.arrear_id]), 'label': 'Schedule', 'css': 'edit'},
        ],
    } for a in arrears]

    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Employee Arrears',
        'columns': ['ID', 'Emp Code', 'Name', 'Arrear Month', 'Gross Shortfall', 'Net Payable', 'Payout (M/Y)', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('create_arrear'), 'add_label': 'Add Arrear',
        'empty_message': 'No arrears on record yet.',
    })


@login_required
def create_arrear(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        form = ArrearForm(request.POST)
        if form.is_valid():
            arrear = form.save(commit=False)
            arrear.company = company
            arrear.created_by = request.user.username
            arrear.compute()
            arrear.save()
            messages.success(request, 'Arrear computed and saved successfully.')
            return redirect('list_arrears')
    else:
        form = ArrearForm()
        form.fields['employee'].queryset = employee_model.objects.filter(CompanyID=company, is_working=True)
        from Aapp.app.increment import Increment
        form.fields['increment'].queryset = Increment.objects.filter(company=company)
        form.fields['increment'].required = False

    return render(request, 'Aapp/works/create_arrear.html', {'form': form, 'company': company})


@login_required
def view_arrear_schedule(request, arrear_id):
    """Print/record view, kept separate from the statutory recompute view below."""
    company = _company(request)
    arrear = get_object_or_404(Arrear, arrear_id=arrear_id, company=company)
    return render(request, 'Aapp/works/arrear_schedule.html', {
        'arrear': arrear,
        'download_url': reverse('download_arrear_schedule', args=[arrear_id]),
    })


@login_required
def download_arrear_schedule(request, arrear_id):
    from django.http import HttpResponse
    from Aapp.app.arrear_pdf import arrear_schedule_pdf

    company = _company(request)
    arrear = get_object_or_404(Arrear, arrear_id=arrear_id, company=company)
    pdf_bytes = arrear_schedule_pdf(arrear)
    return HttpResponse(pdf_bytes, content_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="arrear_{arrear_id}.pdf"'
    })
