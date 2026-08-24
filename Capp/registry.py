"""
Declarative registry driving Capp's generic CRUD engine.

Each entry scopes an existing Aapp/Sapp model to the Company Owner's
single company, without duplicating the ~30 modules of business logic
already written for Aapp. `company_lookup` is a Django ORM filter
kwarg name (supports `__` traversal for models with no direct FK to
Company) used both to filter list querysets and to stamp new records.
"""
from Sapp.app.company import Company, company_statury
from Aapp.app.branch_department import branch, department
from Aapp.app.designation import designation
from Aapp.app.employee import employee
from Aapp.app.attandance import attendance, MinimumWagesOvertimeRegister
from Aapp.app.factory_act import (
    FactoryRegistration, FactoryWhitewashRegister, FactoryVesselExamination,
    LeaveWithWagesRegister, FactoryAccidentRegister, FactoryAnnualReturn,
)
from Aapp.app.contractor import contractor, contractor_payment, contractor_worker
from Aapp.app.contract_labour import (
    ContractLabourRegistration, ContractEmploymentCard,
    ContractServiceCertificate, ContractLabourHalfYearlyReturn,
)
from Aapp.app.gratuity import (
    gratuity_nominee, gratuity_record, gratuity_employer_notice, gratuity_payment_notice,
)
from Aapp.app.maternity import maternity_record, maternity_nomination
from Aapp.app.bonus import bonus_record, bonus_set_on_set_off, bonus_annual_return
from Aapp.app.shops_act import establishment_details
from Aapp.app.wages import wages_fine, wages_deduction
from Aapp.app.salary_processing import salary_slip
from Aapp.app.wage_compliance import MinimumWagesAnnualReturn, PaymentOfWagesAnnualReturn
from Aapp.app.epf_esi import EpfNomination, EpfMonthlyEcr, EsiFamilyMember, EsiContributionReturn
from Aapp.app.labour_welfare import LabourWelfareFundContribution
from Aapp.app.compliance_tracker import StatutoryReturnTracker
from Aapp.app.loans_advances import Loan, Advance
from Aapp.app.increment import Increment
from Aapp.app.arrear import Arrear
from Aapp.app.fnf_settlement import FnFSettlement
from Aapp.app.biometric_device import BiometricDevice, EmployeeDeviceMapping
from Aapp.app.shift import Shift, EmployeeShiftAssignment
from Aapp.app.punch_log import DailyAttendance
from Aapp.app.banking import BankPaymentBatch
from Aapp.app.asset_management import Asset, AssetAssignment, AssetRecovery
from Aapp.app.expense_management import ExpenseClaim

# Fields never shown in the auto-generated form or list; set by the view.
AUDIT_FIELDS = {'created_by', 'updated_by', 'created_at', 'updated_at'}


class Entry:
    def __init__(self, slug, model, company_lookup, label, category, list_fields=None):
        self.slug = slug
        self.model = model
        self.company_lookup = company_lookup          # e.g. 'company', 'companyid', 'CompanyID', 'factory__company'
        self.label = label
        self.category = category
        # First few real fields (excluding pk / company / audit) shown as list columns.
        if list_fields:
            self.list_fields = list_fields
        else:
            skip = {self.company_lookup} if '__' not in self.company_lookup else set()
            names = [
                f.name for f in model._meta.fields
                if f.name not in AUDIT_FIELDS
                and f.name not in skip
                and not f.primary_key
            ]
            self.list_fields = names[:6]


REGISTRY = [
    # ── Masters ──────────────────────────────────────────────────────────
    Entry('branches', branch, 'companyid', 'Branches', 'Masters'),
    Entry('departments', department, 'companyid', 'Departments', 'Masters'),
    Entry('designations', designation, 'company', 'Designations', 'Masters'),

    # ── Employees ────────────────────────────────────────────────────────
    Entry('employees', employee, 'CompanyID', 'Employees', 'Employees'),

    # ── Attendance & Leave ───────────────────────────────────────────────
    # Leave balances (casual/earned/sick/comp) now live directly on
    # attendance — no separate 'leave' entry; edit via the Attendance
    # entry below.
    Entry('attendance', attendance, 'companyid', 'Attendance', 'Attendance'),
    Entry('overtime-wages', MinimumWagesOvertimeRegister, 'attendance__companyid', 'Minimum Wages Overtime Register', 'Attendance'),

    # ── Factory Act 1948 ─────────────────────────────────────────────────
    Entry('factory-registration', FactoryRegistration, 'company', 'Factory Registration', 'Factory Act'),
    Entry('factory-whitewash', FactoryWhitewashRegister, 'factory__company', 'Whitewash Register', 'Factory Act'),
    Entry('factory-vessel', FactoryVesselExamination, 'factory__company', 'Vessel Examination', 'Factory Act'),
    Entry('factory-leave-wages', LeaveWithWagesRegister, 'employee__CompanyID', 'Leave With Wages Register', 'Factory Act'),
    Entry('factory-accident', FactoryAccidentRegister, 'factory__company', 'Accident Register', 'Factory Act'),
    Entry('factory-annual-return', FactoryAnnualReturn, 'factory__company', 'Factory Annual Return', 'Factory Act'),

    # ── Contractor & Contract Labour ─────────────────────────────────────
    Entry('contractors', contractor, 'company', 'Contractors', 'Contract Labour'),
    Entry('contractor-payments', contractor_payment, 'company', 'Contractor Payments', 'Contract Labour'),
    Entry('contractor-workers', contractor_worker, 'company', 'Contractor Workers', 'Contract Labour'),
    Entry('cl-registration', ContractLabourRegistration, 'company', 'Contract Labour Registration', 'Contract Labour'),
    Entry('cl-employment-card', ContractEmploymentCard, 'company', 'Contract Employment Card', 'Contract Labour'),
    Entry('cl-service-certificate', ContractServiceCertificate, 'company', 'Contract Service Certificate', 'Contract Labour'),
    Entry('cl-half-yearly-return', ContractLabourHalfYearlyReturn, 'company', 'Contract Labour Half-Yearly Return', 'Contract Labour'),

    # ── Gratuity ─────────────────────────────────────────────────────────
    Entry('gratuity-nominee', gratuity_nominee, 'company', 'Gratuity Nominee', 'Gratuity'),
    Entry('gratuity-record', gratuity_record, 'company', 'Gratuity Record', 'Gratuity'),
    Entry('gratuity-employer-notice', gratuity_employer_notice, 'company', 'Gratuity Employer Notice', 'Gratuity'),
    Entry('gratuity-payment-notice', gratuity_payment_notice, 'company', 'Gratuity Payment Notice', 'Gratuity'),

    # ── Maternity Benefit ────────────────────────────────────────────────
    Entry('maternity-record', maternity_record, 'company', 'Maternity Record', 'Maternity'),
    Entry('maternity-nomination', maternity_nomination, 'company', 'Maternity Nomination', 'Maternity'),

    # ── Bonus ────────────────────────────────────────────────────────────
    Entry('bonus-record', bonus_record, 'company', 'Bonus Record', 'Bonus'),
    Entry('bonus-set-on-off', bonus_set_on_set_off, 'company', 'Bonus Set-On / Set-Off', 'Bonus'),
    Entry('bonus-annual-return', bonus_annual_return, 'company', 'Bonus Annual Return', 'Bonus'),

    # ── Shops & Establishment Act ────────────────────────────────────────
    Entry('establishment', establishment_details, 'company', 'Establishment Details', 'Shops Act'),
    # Overtime register consolidated into 'overtime-wages' entry above
    # (Aapp.app.attandance.MinimumWagesOvertimeRegister) — shops_act's
    # own overtime_register model was removed as a duplicate.

    # ── Wages ────────────────────────────────────────────────────────────
    # Wages Register is read-only, sourced from salary_slip (payroll
    # engine output) — not a separately-maintained record.
    Entry('wages-record', salary_slip, 'company_id', 'Wages Record (from Salary Processing)', 'Wages'),
    Entry('wages-fine', wages_fine, 'company', 'Wages Fine', 'Wages'),
    Entry('wages-deduction', wages_deduction, 'company', 'Wages Deduction', 'Wages'),
    Entry('mw-annual-return', MinimumWagesAnnualReturn, 'company', 'Minimum Wages Annual Return', 'Wages'),
    Entry('pow-annual-return', PaymentOfWagesAnnualReturn, 'company', 'Payment of Wages Annual Return', 'Wages'),

    # ── EPF / ESI ────────────────────────────────────────────────────────
    Entry('epf-nomination', EpfNomination, 'company', 'EPF Nomination', 'EPF / ESI'),
    Entry('epf-ecr', EpfMonthlyEcr, 'company', 'EPF Monthly ECR', 'EPF / ESI'),
    Entry('esi-family', EsiFamilyMember, 'company', 'ESI Family Member', 'EPF / ESI'),
    Entry('esi-return', EsiContributionReturn, 'company', 'ESI Contribution Return', 'EPF / ESI'),

    # ── Loans & Advances ─────────────────────────────────────────────────
    Entry('loans', Loan, 'company', 'Employee Loans', 'Loans & Advances'),
    Entry('advances', Advance, 'company', 'Employee Advances', 'Loans & Advances'),

    # ── Increment & Arrear ───────────────────────────────────────────────
    Entry('increments', Increment, 'company', 'Employee Increments', 'Increment & Arrear'),
    Entry('arrears', Arrear, 'company', 'Employee Arrears', 'Increment & Arrear'),

    # ── Full & Final Settlement ──────────────────────────────────────────
    Entry('fnf-settlements', FnFSettlement, 'company', 'Full & Final Settlements', 'FnF Settlement'),

    # ── Biometric / RFID Attendance ──────────────────────────────────────
    Entry('biometric-devices', BiometricDevice, 'company', 'Biometric/RFID Devices', 'Biometric Attendance'),
    Entry('device-mappings', EmployeeDeviceMapping, 'device__company', 'Employee Device Mappings', 'Biometric Attendance'),
    Entry('shifts', Shift, 'company', 'Shifts', 'Biometric Attendance'),
    Entry('shift-assignments', EmployeeShiftAssignment, 'employee__CompanyID', 'Shift Assignments', 'Biometric Attendance'),
    Entry('daily-attendance', DailyAttendance, 'company', 'Daily Attendance (Biometric)', 'Biometric Attendance'),

    # ── Banking (NEFT/RTGS/IMPS) ─────────────────────────────────────────
    Entry('bank-payment-batches', BankPaymentBatch, 'company', 'Bank Payment Batches', 'Banking'),

    # ── Assets & Expenses ────────────────────────────────────────────────
    Entry('assets', Asset, 'company', 'Assets', 'Assets & Expenses'),
    Entry('asset-assignments', AssetAssignment, 'asset__company', 'Asset Assignments', 'Assets & Expenses'),
    Entry('asset-recoveries', AssetRecovery, 'company', 'Asset Recoveries', 'Assets & Expenses'),
    Entry('expense-claims', ExpenseClaim, 'company', 'Expense Claims', 'Assets & Expenses'),

    # ── Labour Welfare Fund ──────────────────────────────────────────────
    Entry('lwf-contribution', LabourWelfareFundContribution, 'company', 'Labour Welfare Fund Contribution', 'Labour Welfare'),

    # ── Compliance Tracker ───────────────────────────────────────────────
    Entry('compliance-tracker', StatutoryReturnTracker, 'company', 'Statutory Return Tracker', 'Compliance'),
    Entry('statutory-details', company_statury, 'company', 'Company Statutory Details', 'Compliance'),
]

REGISTRY_BY_SLUG = {e.slug: e for e in REGISTRY}

CATEGORIES = []
for _e in REGISTRY:
    if _e.category not in CATEGORIES:
        CATEGORIES.append(_e.category)
