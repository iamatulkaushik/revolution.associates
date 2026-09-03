"""
Aapp/app/expense_management.py
=================================
Bill upload / reimbursement workflow, per pt_upgrades.md: "Bill upload/
reimbursement workflow with tax-exempt payroll injection".

Approved, tax-exempt reimbursements are pulled into the next salary_slip
as a non-taxable addition (added to net_pay, not to gross_earnings —
keeps it out of PF/ESI/PT/IT computation base, since exempt
reimbursements like medical/travel/conveyance bills aren't taxable
income when supported by bills, per Income Tax Act exemption rules).

Taxable reimbursements (is_tax_exempt=False) instead flow through
gross_earnings normally — handled by NOT auto-injecting them here, left
to the manual 'other_earned' designation field or a future dedicated
gross-side hook.
"""

from datetime import date
from decimal import Decimal

from django.db import models
from django.forms import ModelForm
from django.forms.widgets import Select, NumberInput, DateInput, Textarea, FileInput

from Aapp.app.employee import employee as employee_model
from Sapp.app.company import Company


EXPENSE_CATEGORY_CHOICES = [
    ('medical', 'Medical'),
    ('travel', 'Travel/Conveyance'),
    ('food', 'Food/Meal'),
    ('communication', 'Communication (Phone/Internet)'),
    ('training', 'Training/Professional Development'),
    ('other', 'Other'),
]

APPROVAL_STATUS_CHOICES = [
    ('pending', 'Pending Approval'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('paid', 'Paid (Injected into Payroll)'),
]

# Categories that are typically tax-exempt when bill-supported, per
# Income Tax Act — used as the default when creating a new expense;
# HR can override per-claim if the specific bill doesn't qualify.
DEFAULT_TAX_EXEMPT_CATEGORIES = {'medical', 'travel', 'communication'}


class ExpenseClaim(models.Model):
    """One reimbursement claim, with an attached bill/receipt file."""
    expense_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(employee_model, on_delete=models.CASCADE, related_name='expense_claims')
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    category = models.CharField(max_length=15, choices=EXPENSE_CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    expense_date = models.DateField(help_text="Date the expense was incurred")
    description = models.CharField(max_length=500, blank=True)
    bill_file = models.FileField(upload_to='expense_bills/%Y/%m/', help_text="Scanned bill/receipt")

    is_tax_exempt = models.BooleanField(default=True)
    status = models.CharField(max_length=10, choices=APPROVAL_STATUS_CHOICES, default='pending')
    approved_by = models.CharField(max_length=50, null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)

    payout_month = models.PositiveSmallIntegerField(null=True, blank=True,
                                                      help_text="Set when injected into a salary_slip")
    payout_year = models.PositiveIntegerField(null=True, blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Aapp'
        db_table = 'aa_expense_claims'
        ordering = ['-submitted_at']
        verbose_name = "Expense Claim"

    def __str__(self):
        return f"Claim #{self.expense_id} - {self.employee.name} - Rs.{self.amount} ({self.get_category_display()})"


class ExpenseClaimForm(ModelForm):
    class Meta:
        model = ExpenseClaim
        fields = ['category', 'amount', 'expense_date', 'description', 'bill_file', 'is_tax_exempt']
        widgets = {
            'category': Select(attrs={'class': 'form-control'}),
            'amount': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'expense_date': DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'bill_file': FileInput(attrs={'class': 'form-control'}),
        }


def get_approved_reimbursement_for_month(employee_obj, month, year):
    """
    Sum of 'approved' tax-exempt claims for this employee not yet paid
    out, that should be injected into this month's payroll. Marks them
    'paid' with the given payout month/year as a side effect — call
    this exactly once per payroll run per employee, from
    calculate_employee_salary(), not repeatedly.
    """
    claims = ExpenseClaim.objects.filter(
        employee=employee_obj, status='approved', is_tax_exempt=True
    )
    total = claims.aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

    if total > 0:
        claims.update(status='paid', payout_month=month, payout_year=year)

    return total


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
def list_expense_claims(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    status_filter = request.GET.get('status', '')
    claims = ExpenseClaim.objects.filter(company=company).select_related('employee')
    if status_filter:
        claims = claims.filter(status=status_filter)
    claims = claims.order_by('-submitted_at')

    rows = [{
        'cells': [c.employee.employeecode, c.employee.name, c.get_category_display(),
                  f"Rs. {c.amount}", c.expense_date, 'Yes' if c.is_tax_exempt else 'No', c.get_status_display()],
        'actions': (
            [{'url': reverse('approve_expense_claim', args=[c.expense_id]), 'label': 'Approve'},
             {'url': reverse('reject_expense_claim', args=[c.expense_id]), 'label': 'Reject'}]
            if c.status == 'pending' else
            [{'url': c.bill_file.url, 'label': 'View Bill'}] if c.bill_file else []
        ),
    } for c in claims]

    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Expense Claims',
        'columns': ['Emp Code', 'Name', 'Category', 'Amount', 'Date', 'Tax Exempt', 'Status'],
        'rows': rows, 'company': company,
        'add_url': reverse('create_expense_claim'), 'add_label': 'Submit Expense Claim',
        'empty_message': 'No expense claims submitted yet.',
    })


@login_required
def create_expense_claim(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')

    # Employee submitting on their own behalf — assumes the logged-in
    # user maps to an employee record via session, matching this
    # codebase's session-based company context pattern. Falls back to
    # letting HR pick the employee explicitly if no such link exists.
    if request.method == 'POST':
        form = ExpenseClaimForm(request.POST, request.FILES)
        employee_id = request.POST.get('employee_id')
        emp = employee_model.objects.filter(pk=employee_id, CompanyID=company).first() if employee_id else None

        if form.is_valid() and emp:
            claim = form.save(commit=False)
            claim.employee = emp
            claim.company = company
            claim.save()
            messages.success(request, 'Expense claim submitted for approval.')
            return redirect('list_expense_claims')
        elif not emp:
            messages.error(request, 'Please select a valid employee.')
    else:
        form = ExpenseClaimForm()

    employees = employee_model.objects.filter(CompanyID=company, is_working=True)
    return render(request, 'Aapp/works/create_expense_claim.html', {
        'form': form, 'company': company, 'employees': employees
    })


@login_required
def approve_expense_claim(request, expense_id):
    company = _company(request)
    claim = get_object_or_404(ExpenseClaim, expense_id=expense_id, company=company)
    claim.status = 'approved'
    claim.approved_by = request.user.username
    claim.save(update_fields=['status', 'approved_by', 'updated_at'])
    messages.success(request, 'Expense claim approved. It will be added to the next payroll run.')
    return redirect('list_expense_claims')


@login_required
def reject_expense_claim(request, expense_id):
    company = _company(request)
    claim = get_object_or_404(ExpenseClaim, expense_id=expense_id, company=company)
    claim.status = 'rejected'
    claim.rejection_reason = request.POST.get('reason', '')
    claim.save(update_fields=['status', 'rejection_reason', 'updated_at'])
    messages.success(request, 'Expense claim rejected.')
    return redirect('list_expense_claims')
