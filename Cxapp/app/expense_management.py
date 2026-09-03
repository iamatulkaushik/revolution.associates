"""
Cxapp/app/expense_management.py
==================================
Expense/reimbursement claims for the Cxapp portal — mirrors
Aapp.app.expense_management but scoped to CxOwnerProfile/CxEmployee.

Approved tax-exempt claims are injected into CxSalary.process()'s
total_amount, same additive-after-deductions treatment as Aapp (kept
out of the EPF/ESI wage base).
"""

from decimal import Decimal

from django.db import models
from django.forms import ModelForm
from django.forms.widgets import Select, NumberInput, DateInput, Textarea, FileInput

from Cxapp.app.employee import CxEmployee

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


class CxExpenseClaim(models.Model):
    expense_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(CxEmployee, on_delete=models.CASCADE, related_name='expense_claims')
    company = models.ForeignKey('Cxapp.CxOwnerProfile', on_delete=models.CASCADE)

    category = models.CharField(max_length=15, choices=EXPENSE_CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    expense_date = models.DateField()
    description = models.CharField(max_length=500, blank=True)
    bill_file = models.FileField(upload_to='cx_expense_bills/%Y/%m/')

    is_tax_exempt = models.BooleanField(default=True)
    status = models.CharField(max_length=10, choices=APPROVAL_STATUS_CHOICES, default='pending')
    approved_by = models.CharField(max_length=50, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)

    payout_month = models.PositiveSmallIntegerField(null=True, blank=True)
    payout_year = models.PositiveIntegerField(null=True, blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_expense_claims'
        ordering = ['-submitted_at']
        verbose_name = "Expense Claim"

    def __str__(self):
        return f"Claim #{self.expense_id} - {self.employee.name} - Rs.{self.amount}"


class CxExpenseClaimForm(ModelForm):
    class Meta:
        model = CxExpenseClaim
        fields = ['category', 'amount', 'expense_date', 'description', 'bill_file', 'is_tax_exempt']
        widgets = {
            'category': Select(attrs={'class': 'form-control'}),
            'amount': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'expense_date': DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'bill_file': FileInput(attrs={'class': 'form-control'}),
        }


def get_approved_reimbursement_for_month(employee_obj, month, year):
    """Marks matching claims 'paid' as a side effect — call once per payroll run."""
    claims = CxExpenseClaim.objects.filter(
        employee=employee_obj, status='approved', is_tax_exempt=True
    )
    total = claims.aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    if total > 0:
        claims.update(status='paid', payout_month=month, payout_year=year)
    return total


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


def cxapp_list_expense_claims(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_list_expense_claims)(request)


def _list_expense_claims(request):
    if not _can_manage_payroll(request):
        messages.error(request, 'You do not have permission to view expense claims.')
        return redirect('cxapp_dashboard')

    owner_profile = request.cx_owner_profile
    status_filter = request.GET.get('status', '')
    claims = CxExpenseClaim.objects.filter(company=owner_profile).select_related('employee')
    if status_filter:
        claims = claims.filter(status=status_filter)
    claims = claims.order_by('-submitted_at')

    return render(request, 'Cxapp/expenses/claim_list.html', {'claims': claims})


def cxapp_create_expense_claim(request):
    from Cxapp.views import cx_login_required
    return cx_login_required(_create_expense_claim)(request)


def _create_expense_claim(request):
    owner_profile = request.cx_owner_profile

    if request.method == 'POST':
        form = CxExpenseClaimForm(request.POST, request.FILES)
        employee_id = request.POST.get('employee_id')
        emp = CxEmployee.objects.filter(pk=employee_id, company=owner_profile).first() if employee_id else None

        if form.is_valid() and emp:
            claim = form.save(commit=False)
            claim.employee = emp
            claim.company = owner_profile
            claim.save()
            messages.success(request, 'Expense claim submitted for approval.')
            return redirect('cxapp_list_expense_claims')
        elif not emp:
            messages.error(request, 'Please select a valid employee.')
    else:
        form = CxExpenseClaimForm()

    employees = CxEmployee.objects.filter(company=owner_profile, is_working=True)
    return render(request, 'Cxapp/expenses/create_claim.html', {'form': form, 'employees': employees})


def cxapp_approve_expense_claim(request, expense_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_approve_expense_claim)(request, expense_id)


def _approve_expense_claim(request, expense_id):
    owner_profile = request.cx_owner_profile
    claim = get_object_or_404(CxExpenseClaim, expense_id=expense_id, company=owner_profile)
    claim.status = 'approved'
    claim.approved_by = getattr(request.cx_sub_user, 'username', 'Owner')
    claim.save(update_fields=['status', 'approved_by', 'updated_at'])
    messages.success(request, 'Expense claim approved.')
    return redirect('cxapp_list_expense_claims')


def cxapp_reject_expense_claim(request, expense_id):
    from Cxapp.views import cx_login_required
    return cx_login_required(_reject_expense_claim)(request, expense_id)


def _reject_expense_claim(request, expense_id):
    owner_profile = request.cx_owner_profile
    claim = get_object_or_404(CxExpenseClaim, expense_id=expense_id, company=owner_profile)
    claim.status = 'rejected'
    claim.rejection_reason = request.POST.get('reason', '')
    claim.save(update_fields=['status', 'rejection_reason', 'updated_at'])
    messages.success(request, 'Expense claim rejected.')
    return redirect('cxapp_list_expense_claims')
