from django import forms
from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from Sapp.app.company import Company
from Sapp.app.user import associateuser
from Aapp.app.employee import employee

MONTH_CHOICES = [
    (1,'January'),(2,'February'),(3,'March'),(4,'April'),
    (5,'May'),(6,'June'),(7,'July'),(8,'August'),
    (9,'September'),(10,'October'),(11,'November'),(12,'December'),
]


# ── Associate-only guard ──────────────────────────────────────────────────────

def _get_associate(request):
    try:
        return associateuser.objects.get(user=request.user)
    except associateuser.DoesNotExist:
        return None

def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None

def _guard(request):
    """Returns (associate, company) or (None, None) with error message set."""
    associate = _get_associate(request)
    if not associate:
        messages.error(request, 'Access restricted to associates only.')
        return None, None
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return None, None
    return associate, company


# ── Model ─────────────────────────────────────────────────────────────────────

class employee_leave(models.Model):
    leaveid        = models.AutoField(primary_key=True)
    employee_id    = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='employee_id', related_name='leaves')
    emp_code       = models.CharField(max_length=20)
    companyid      = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='companyid')
    salary_month   = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    salary_year    = models.PositiveSmallIntegerField()
    leaves_earned  = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    leave_availed  = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    leave_balance  = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    leave_lapsed  = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    leave_encased = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    encashmanent_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    wages_paid     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='leave_created')
    created_date   = models.DateTimeField(auto_now_add=True)
    updated_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='leave_updated')
    updated_date   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employee_leave'
        unique_together = ('employee_id', 'salary_month', 'salary_year')
        ordering = ['-salary_year', '-salary_month']

    def __str__(self):
        return f"{self.emp_code} — {self.get_salary_month_display()} {self.salary_year}"

    def save(self, *args, **kwargs):
        self.leave_balance = self.leaves_earned - self.leave_availed
        super().save(*args, **kwargs)


# ── Form ──────────────────────────────────────────────────────────────────────

class LeaveForm(forms.ModelForm):
    class Meta:
        model  = employee_leave
        fields = ['salary_month', 'salary_year', 'leaves_earned', 'leave_availed', 'wages_paid']
        widgets = {
            'salary_month': forms.Select(choices=MONTH_CHOICES),
            'salary_year':  forms.NumberInput(attrs={'min': 2026, 'max': 2032}),
        }


# ── list ──────────────────────────────────────────────────────────────────────

@login_required
def list_leave(request):
    associate, company = _guard(request)
    if not associate:
        return redirect('aapp_dashboard')

    records = employee_leave.objects.filter(companyid=company).select_related('employee_id')

    month = request.GET.get('month')
    year = request.GET.get('year')
    if month:
        records = records.filter(salary_month=month)
    if year:
        records = records.filter(salary_year=year)

    rows = [{
        'cells': [r.emp_code, r.get_salary_month_display(), r.salary_year, r.leaves_earned,
                  r.leave_availed, r.leave_balance, r.wages_paid],
        'actions': [
            {'url': reverse('update_leave', args=[r.leaveid]), 'label': 'Edit', 'css': 'edit'},
            {'url': reverse('delete_leave', args=[r.leaveid]), 'label': 'Delete', 'css': 'delete'},
        ],
    } for r in records]
    return render(request, 'Aapp/generic/list.html', {
        'page_title': 'Employee Leave Records',
        'columns': ['Employee Code', 'Month', 'Year', 'Earned', 'Availed', 'Balance', 'Wages Paid'],
        'rows': rows, 'company': company,
        'add_url': reverse('add_leave'), 'add_label': 'Add Leave Record',
        'empty_message': 'No leave records yet.',
    })


# ── add ───────────────────────────────────────────────────────────────────────

@login_required
def add_leave(request):
    associate, company = _guard(request)
    if not associate:
        return redirect('aapp_dashboard')

    employees = employee.objects.filter(CompanyID=company, is_working=True).order_by('name')

    if request.method == 'POST':
        p = request.POST
        emp = get_object_or_404(employee, employeeid=p.get('employee_id'), CompanyID=company)
        month = int(p.get('salary_month', 0))
        year = int(p.get('salary_year', 0))

        if employee_leave.objects.filter(employee_id=emp, salary_month=month, salary_year=year).exists():
            messages.error(request, f"Leave record for {emp.name} — {month}/{year} already exists.")
        else:
            try:
                earned = float(p.get('leaves_earned', 0) or 0)
                availed = float(p.get('leave_availed', 0) or 0)
                employee_leave.objects.create(
                    employee_id=emp,
                    emp_code=emp.employeecode,
                    companyid=company,
                    salary_month=month,
                    salary_year=year,
                    leaves_earned=earned,
                    leave_availed=availed,
                    leave_balance=earned - availed,
                    wages_paid=p.get('wages_paid', 0) or 0,
                    created_by=request.user,
                )
                messages.success(request, f"Leave record for {emp.name} saved.")
                return redirect('list_leave')
            except Exception as e:
                messages.error(request, f"Error: {e}")

    return render(request, 'Aapp/generic/form.html', {
        'form': LeaveForm(), 'employees': employees, 'company': company,
        'page_title': 'Add Leave Record',
        'cancel_url': reverse('list_leave'),
    })


# ── update ────────────────────────────────────────────────────────────────────

@login_required
def update_leave(request, leave_id):
    associate, company = _guard(request)
    if not associate:
        return redirect('aapp_dashboard')

    rec = get_object_or_404(employee_leave, leaveid=leave_id, companyid=company)

    if request.method == 'POST':
        p = request.POST
        try:
            earned = float(p.get('leaves_earned', rec.leaves_earned) or 0)
            availed = float(p.get('leave_availed', rec.leave_availed) or 0)
            rec.salary_month = int(p.get('salary_month', rec.salary_month))
            rec.salary_year = int(p.get('salary_year', rec.salary_year))
            rec.leaves_earned = earned
            rec.leave_availed = availed
            rec.leave_balance = earned - availed
            rec.wages_paid = p.get('wages_paid', rec.wages_paid) or rec.wages_paid
            rec.updated_by = request.user
            rec.save()
            messages.success(request, "Leave record updated.")
            return redirect('list_leave')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    form = LeaveForm(instance=rec)
    return render(request, 'Aapp/generic/form.html', {
        'form': form, 'rec': rec, 'company': company,
        'page_title': f'Edit Leave Record — {rec.emp_code}',
        'cancel_url': reverse('list_leave'),
    })


# ── delete ────────────────────────────────────────────────────────────────────

@login_required
def delete_leave(request, leave_id):
    associate, company = _guard(request)
    if not associate:
        return redirect('aapp_dashboard')

    rec = get_object_or_404(employee_leave, leaveid=leave_id, companyid=company)

    if request.method == 'POST':
        rec.delete()
        messages.success(request, "Leave record deleted.")
        return redirect('list_leave')

    return render(request, 'Aapp/generic/confirm.html', {
        'company': company,
        'page_title': 'Delete Leave Record',
        'confirm_message': f'Delete leave record for <strong>{rec.emp_code}</strong> — '
                            f'{rec.get_salary_month_display()} {rec.salary_year}?',
        'cancel_url': reverse('list_leave'),
    })
