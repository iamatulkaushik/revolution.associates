from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from Sapp.app.company import Company
from Aapp.app.employee import employee


RELATIONSHIP_CHOICES = [
    ('spouse',          'Spouse'),
    ('son',             'Son'),
    ('daughter',        'Daughter'),
    ('father',          'Father'),
    ('mother',          'Mother'),
    ('brother',         'Brother'),
    ('sister',          'Sister'),
    ('other',           'Other'),
]

GRATUITY_REASON_CHOICES = [
    ('superannuation',  'Superannuation'),
    ('retirement',      'Retirement'),
    ('resignation',     'Resignation'),
    ('death',           'Death'),
    ('disablement',     'Disablement'),
    ('termination',     'Termination'),
]


# ── Models ────────────────────────────────────────────────────────────────────

class gratuity_nominee(models.Model):
    nominee_id      = models.AutoField(primary_key=True)
    company         = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    employee        = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID', related_name='nominees')
    nominee_name    = models.CharField(max_length=255)
    relationship    = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    address         = models.TextField()
    share_percent   = models.DecimalField(max_digits=5, decimal_places=2,
                        help_text='Share percentage (all nominees must total 100%)')
    date_of_birth   = models.DateField(null=True, blank=True)
    gender          = models.CharField(max_length=10, choices=[('Male','Male'),('Female','Female'),('Other','Other')])
    aadhar_number   = models.CharField(max_length=12, blank=True,
                        help_text='For identity verification (Form F — Gratuity Act)')
    pan_number      = models.CharField(max_length=10, blank=True)
    bank_account    = models.CharField(max_length=20, blank=True)
    bank_ifsc       = models.CharField(max_length=11, blank=True)
    bank_name       = models.CharField(max_length=255, blank=True)
    is_minor        = models.BooleanField(default=False,
                        help_text='If minor, guardian details required as per Form F')
    guardian_name   = models.CharField(max_length=255, blank=True)
    guardian_relationship = models.CharField(max_length=100, blank=True)
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='nominees_created')
    created_date    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gratuity_nominee'
        ordering = ['employee', 'nominee_name']

    def __str__(self):
        return f"{self.employee.employeecode} — {self.nominee_name} ({self.get_relationship_display()})"


class gratuity_record(models.Model):
    gratuity_id         = models.AutoField(primary_key=True)
    company             = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    employee            = models.ForeignKey(employee, on_delete=models.CASCADE, db_column='EmployeeID', related_name='gratuity')

    # Service details
    date_of_joining     = models.DateField(help_text='Auto-filled from employee record')
    date_of_leaving     = models.DateField(help_text='Auto-filled from employee record')
    years_of_service    = models.DecimalField(max_digits=5, decimal_places=2,
                            help_text='Calculated: min 5 years required for eligibility')

    # Salary basis
    basic_salary        = models.DecimalField(max_digits=10, decimal_places=2,
                            help_text='Last drawn basic + DA (basis for gratuity calculation)')
    da                  = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Gratuity calculation: (Basic+DA) × 15/26 × Years of Service
    gratuity_amount     = models.DecimalField(max_digits=12, decimal_places=2,
                            help_text='Formula: (Basic+DA) × 15/26 × Years')
    reason              = models.CharField(max_length=30, choices=GRATUITY_REASON_CHOICES)
    remarks             = models.CharField(max_length=500, blank=True)

    is_paid             = models.BooleanField(default=False)
    payment_date        = models.DateField(null=True, blank=True)
    created_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='gratuity_created')
    created_date        = models.DateTimeField(auto_now_add=True)
    updated_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='gratuity_updated')
    updated_date        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gratuity_record'
        unique_together = ('employee', 'date_of_leaving')
        ordering = ['-date_of_leaving']

    def __str__(self):
        return f"{self.employee.employeecode} — Gratuity ₹{self.gratuity_amount}"

    @staticmethod
    def calculate_gratuity(basic, da, years):
        return round((float(basic) + float(da)) * 15 / 26 * float(years), 2)


# ── Helper ────────────────────────────────────────────────────────────────────

def _company(request):
    cid = request.session.get('selected_company_id')
    return Company.objects.filter(company_id=cid).first() if cid else None


# ── Nominee Views ─────────────────────────────────────────────────────────────

@login_required
def list_nominees(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    nominees = gratuity_nominee.objects.filter(company=company).select_related('employee')
    return render(request, 'Aapp/gratuity/list_nominees.html', {'nominees': nominees, 'company': company})


@login_required
def add_nominee(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    employees = employee.objects.filter(CompanyID=company, is_working=True).order_by('name')

    if request.method == 'POST':
        p   = request.POST
        emp = get_object_or_404(employee, employeeid=p.get('employee_id'), CompanyID=company)
        gratuity_nominee.objects.create(
            company=company, employee=emp,
            nominee_name=p.get('nominee_name'),
            relationship=p.get('relationship'),
            address=p.get('address'),
            share_percent=p.get('share_percent', 100),
            date_of_birth=p.get('date_of_birth') or None,
            gender=p.get('gender'),
            aadhar_number=p.get('aadhar_number', ''),
            pan_number=p.get('pan_number', ''),
            bank_account=p.get('bank_account', ''),
            bank_ifsc=p.get('bank_ifsc', ''),
            bank_name=p.get('bank_name', ''),
            is_minor=p.get('is_minor') == 'on',
            guardian_name=p.get('guardian_name', ''),
            guardian_relationship=p.get('guardian_relationship', ''),
            created_by=request.user,
        )
        messages.success(request, f'Nominee added for {emp.name}.')
        return redirect('Aapp:list_nominees')

    return render(request, 'Aapp/gratuity/add_nominee.html', {
        'employees': employees,
        'relationships': RELATIONSHIP_CHOICES,
        'company': company,
    })


@login_required
def update_nominee(request, nominee_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    nom = get_object_or_404(gratuity_nominee, nominee_id=nominee_id, company=company)

    if request.method == 'POST':
        p = request.POST
        nom.nominee_name          = p.get('nominee_name', nom.nominee_name)
        nom.relationship          = p.get('relationship', nom.relationship)
        nom.address               = p.get('address', nom.address)
        nom.share_percent         = p.get('share_percent', nom.share_percent)
        nom.date_of_birth         = p.get('date_of_birth') or nom.date_of_birth
        nom.gender                = p.get('gender', nom.gender)
        nom.aadhar_number         = p.get('aadhar_number', nom.aadhar_number)
        nom.pan_number            = p.get('pan_number', nom.pan_number)
        nom.bank_account          = p.get('bank_account', nom.bank_account)
        nom.bank_ifsc             = p.get('bank_ifsc', nom.bank_ifsc)
        nom.bank_name             = p.get('bank_name', nom.bank_name)
        nom.is_minor              = p.get('is_minor') == 'on'
        nom.guardian_name         = p.get('guardian_name', nom.guardian_name)
        nom.guardian_relationship = p.get('guardian_relationship', nom.guardian_relationship)
        nom.save()
        messages.success(request, 'Nominee updated.')
        return redirect('Aapp:list_nominees')

    return render(request, 'Aapp/gratuity/update_nominee.html', {
        'nom': nom, 'relationships': RELATIONSHIP_CHOICES,
    })


@login_required
def delete_nominee(request, nominee_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    nom = get_object_or_404(gratuity_nominee, nominee_id=nominee_id, company=company)
    if request.method == 'POST':
        nom.delete()
        messages.success(request, 'Nominee deleted.')
        return redirect('Aapp:list_nominees')
    return render(request, 'Aapp/gratuity/delete_nominee.html', {'nom': nom})


# ── Gratuity Record Views ─────────────────────────────────────────────────────

@login_required
def list_gratuity(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    records = gratuity_record.objects.filter(company=company).select_related('employee')
    return render(request, 'Aapp/gratuity/list_gratuity.html', {'records': records, 'company': company})


@login_required
def add_gratuity(request):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    # Only separated employees
    employees = employee.objects.filter(CompanyID=company, is_working=False).order_by('name')

    if request.method == 'POST':
        p   = request.POST
        emp = get_object_or_404(employee, employeeid=p.get('employee_id'), CompanyID=company)

        doj = emp.dateofjoining
        dol = emp.dateofleaving or doj
        years = round((dol - doj).days / 365.25, 2)
        basic = float(p.get('basic_salary', 0))
        da    = float(p.get('da', 0))
        amount = gratuity_record.calculate_gratuity(basic, da, years)

        gratuity_record.objects.create(
            company=company, employee=emp,
            date_of_joining=doj, date_of_leaving=dol,
            years_of_service=years,
            basic_salary=basic, da=da,
            gratuity_amount=amount,
            reason=p.get('reason'),
            remarks=p.get('remarks', ''),
            created_by=request.user,
        )
        messages.success(request, f'Gratuity record created for {emp.name} — ₹{amount}.')
        return redirect('Aapp:list_gratuity')

    return render(request, 'Aapp/gratuity/add_gratuity.html', {
        'employees': employees,
        'reasons': GRATUITY_REASON_CHOICES,
        'company': company,
    })


@login_required
def mark_gratuity_paid(request, gratuity_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(gratuity_record, gratuity_id=gratuity_id, company=company)
    if request.method == 'POST':
        from datetime import date
        rec.is_paid      = True
        rec.payment_date = request.POST.get('payment_date') or date.today()
        rec.updated_by   = request.user
        rec.save()
        messages.success(request, f'Gratuity marked as paid for {rec.employee.name}.')
        return redirect('Aapp:list_gratuity')
    return render(request, 'Aapp/gratuity/mark_gratuity_paid.html', {'rec': rec})


@login_required
def delete_gratuity(request, gratuity_id):
    company = _company(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    rec = get_object_or_404(gratuity_record, gratuity_id=gratuity_id, company=company, is_paid=False)
    if request.method == 'POST':
        rec.delete()
        messages.success(request, 'Gratuity record deleted.')
        return redirect('Aapp:list_gratuity')
    return render(request, 'Aapp/gratuity/delete_gratuity.html', {'rec': rec})
