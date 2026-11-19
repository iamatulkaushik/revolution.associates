"""
Capp/billing_models.py
======================
Contractor Billing (manpower service owner) — Capp only.
"""
from decimal import Decimal
from django.db import models
from Sapp.app.company import Company

ESI_BASE_CHOICES = [('BASIC', 'Basic'), ('GROSS', 'Gross')]
FILE_TYPE_CHOICES = [('XLSX', 'Excel'), ('CSV', 'CSV'), ('TXT', 'Text')]
SOURCE_FIELDS = [
    ('serial', 'Serial No'), ('emp_code', 'Employee ID'), ('name', 'Name'),
    ('father_name', 'Father Name'), ('department', 'Department'), ('ifsc', 'IFSC'), ('account', 'Account No'),
    ('net_pay', 'Net Pay (whole rupee)'), ('mobile', 'Mobile'),
    ('address', 'Address'), ('narration', 'Narration'),
    ('pay_date', 'Payment Date'), ('debit_account', 'Company Debit A/c'),
    ('fixed', 'Fixed Value'),
]


class BillingClient(models.Model):
    """Principal company the contractor bills."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE,
                                related_name='billing_clients', db_column='CompanyID')
    name = models.CharField(max_length=255)
    gstin = models.CharField(max_length=15, blank=True)
    address = models.CharField(max_length=255, blank=True)
    service_charge_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    gst_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('18.00'))
    esi_base = models.CharField(max_length=5, choices=ESI_BASE_CHOICES, default='GROSS')
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'Capp'
        db_table = 'ca_billing_client'
        unique_together = ('company', 'name')

    def __str__(self):
        return self.name


class BankFormat(models.Model):
    """Bank upload format, stored per company."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE,
                                related_name='bank_formats', db_column='CompanyID')
    bank_name = models.CharField(max_length=100)
    ifsc_prefix = models.CharField(max_length=4, help_text='e.g. CNRB, BARB, SBIN')
    file_type = models.CharField(max_length=4, choices=FILE_TYPE_CHOICES, default='XLSX')
    delimiter = models.CharField(max_length=2, default=',', blank=True)
    has_header = models.BooleanField(default=True)
    add_total_row = models.BooleanField(default=False)
    sample_file = models.FileField(upload_to='bank_format_samples/', null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'Capp'
        db_table = 'ca_bank_format'
        unique_together = ('company', 'ifsc_prefix')

    def __str__(self):
        return f'{self.bank_name} ({self.ifsc_prefix})'


class BankFormatColumn(models.Model):
    """One output column of a bank format, in order."""
    bank_format = models.ForeignKey(BankFormat, on_delete=models.CASCADE, related_name='columns')
    position = models.PositiveSmallIntegerField()
    header = models.CharField(max_length=100, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_FIELDS)
    fixed_value = models.CharField(max_length=100, blank=True)
    width = models.PositiveSmallIntegerField(null=True, blank=True, help_text='TXT padding')

    class Meta:
        app_label = 'Capp'
        db_table = 'ca_bank_format_column'
        ordering = ['position']
        unique_together = ('bank_format', 'position')


class EmployeeDeduction(models.Model):
    """Custom deduction: loan/advance recur monthly, selective is one-time."""
    KIND_CHOICES = [('RECURRING', 'Recurring (loan/advance)'), ('ONCE', 'One-time')]
    company = models.ForeignKey(Company, on_delete=models.CASCADE,
                                related_name='emp_deductions', db_column='CompanyID')
    employee = models.ForeignKey('Aapp.employee', on_delete=models.CASCADE,
                                 related_name='custom_deductions', db_column='EmployeeID')
    title = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default='ONCE')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    emi_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    start_month = models.DateField(help_text='First of month')
    is_paused = models.BooleanField(default=False)
    is_closed = models.BooleanField(default=False)
    last_applied = models.DateField(null=True, blank=True,
                                    help_text='Month (1st) whose payroll already reduced the balance')
    remarks = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'Capp'
        db_table = 'ca_emp_deduction'

    def amount_for_month(self):
        """Amount to deduct this month. Last EMI capped at balance."""
        if self.is_closed or self.is_paused or self.balance <= 0:
            return Decimal('0')
        if self.kind == 'ONCE':
            return self.balance
        return min(self.emi_amount or self.balance, self.balance)


class ClientEmployee(models.Model):
    """Employee deployed at a billing client. One client per employee."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_column='CompanyID')
    client = models.ForeignKey(BillingClient, on_delete=models.CASCADE, related_name='deployed')
    employee = models.OneToOneField('Aapp.employee', on_delete=models.CASCADE,
                                    related_name='billing_deployment', db_column='EmployeeID')

    class Meta:
        app_label = 'Capp'
        db_table = 'ca_client_employee'


class Invoice(models.Model):
    KIND_CHOICES = [('SALARY', 'Salary bill'), ('OT', 'Overtime bill')]
    STATUS_CHOICES = [('DRAFT', 'Draft'), ('ISSUED', 'Issued'), ('CANCELLED', 'Cancelled')]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='invoices',
                                db_column='CompanyID')
    client = models.ForeignKey(BillingClient, on_delete=models.PROTECT, related_name='invoices')
    kind = models.CharField(max_length=6, choices=KIND_CHOICES)
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    fy = models.CharField(max_length=7)                       # e.g. 2026-27
    seq = models.PositiveIntegerField()
    number = models.CharField(max_length=30)
    invoice_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    esi_base = models.CharField(max_length=5, choices=ESI_BASE_CHOICES, default='GROSS')
    service_charge_pct = models.DecimalField(max_digits=5, decimal_places=2)
    gst_pct = models.DecimalField(max_digits=5, decimal_places=2)
    pay = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    epf_employer = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    esi_employer = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    lwf = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    att_bonus = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    service_charge = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    subtotal = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    sgst = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    cgst = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    extra_label = models.CharField(max_length=60, blank=True)
    extra_charges = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    # payment tracking
    received_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tds_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    received_on = models.DateField(null=True, blank=True)
    payment_ref = models.CharField(max_length=60, blank=True)
    created_by = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'Capp'
        db_table = 'ca_invoice'
        unique_together = [('company', 'fy', 'seq')]
        ordering = ['-invoice_date', '-seq']

    @property
    def outstanding(self):
        return self.total - self.received_amount - self.tds_amount

    def __str__(self):
        return self.number


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    employee = models.ForeignKey('Aapp.employee', on_delete=models.SET_NULL, null=True,
                                 db_column='EmployeeID')
    emp_code = models.CharField(max_length=20)
    name = models.CharField(max_length=255)
    designation = models.CharField(max_length=255, blank=True)
    paid_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    ot_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    gross = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    epf_employer = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    esi_employer = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    lwf = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    att_bonus = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    ot_pay = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    class Meta:
        app_label = 'Capp'
        db_table = 'ca_invoice_line'
        ordering = ['emp_code']
