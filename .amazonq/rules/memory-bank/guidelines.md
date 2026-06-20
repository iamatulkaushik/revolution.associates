# Development Guidelines

## Code Quality Standards

### File Organization
- **Modular Structure**: Business logic separated into app/ subdirectories within Django apps
  - Example: `Sapp/app/user.py`, `Sapp/app/company.py`, `Aapp/app/employee.py`
  - Main `models.py` imports from app/ modules for centralized model registration
- **Empty __init__.py**: All package __init__.py files are empty (no initialization code)
- **Separation of Concerns**: Models, views, forms, and utilities clearly separated

### Naming Conventions
- **Models**: PascalCase for classes (Company, associateuser, SubUser, employee)
- **Database Tables**: Explicit db_table in Meta class (lowercase or mixed case)
  - Examples: `db_table = 'Company'`, `db_table = 'associate_users'`, `db_table = 'employee'`
- **Foreign Keys**: Explicit db_column for database column names
  - Example: `state_id = models.ForeignKey(State, db_column="StateID", ...)`
- **Fields**: snake_case for model fields (company_name, date_of_birth, mobile)
- **Functions**: snake_case for all functions (create_associate_user, can_user_access_system)
- **Views**: snake_case for view functions (list_employee, create_company, alter_associate)
- **URL Names**: snake_case with underscores (list_company, create_associate, alter_employee)

### Documentation Standards
- **Docstrings**: Module-level docstrings for complex functions
  - Example: `"""Check whether any type of user is allowed to access the system."""`
- **Inline Comments**: Used for clarification, especially for "Fixed:" notes
  - Example: `# Fixed: enforce suspension / disabled check at login time`
- **Section Separators**: Comment blocks with dashes for visual organization
  ```python
  # ---------------------------------------------------------------------------
  # Dashboard
  # ---------------------------------------------------------------------------
  ```
- **Helper Function Markers**: Compact separator style
  ```python
  # ── helpers ──────────────────────────────────────────────────────────────────
  ```

### Code Formatting
- **Line Length**: Generally kept under 100-120 characters
- **Indentation**: 4 spaces (Python standard)
- **Blank Lines**: 2 blank lines between top-level functions/classes
- **Import Organization**:
  1. Standard library imports
  2. Django imports
  3. Third-party imports
  4. Local app imports
  ```python
  import logging
  from datetime import datetime
  
  from django.db import models
  from django.contrib.auth.models import User
  
  from Sapp.app.company import Company
  ```

## Semantic Patterns

### Django Model Patterns

#### 1. Audit Fields Pattern
Every major model includes audit fields:
```python
created_at = models.DateTimeField(auto_now_add=True)
updated_at = models.DateTimeField(auto_now=True)
```

#### 2. Suspension/Disable Pattern
User-related models implement suspension and disable functionality:
```python
is_active = models.BooleanField(default=True)
is_suspended = models.BooleanField(default=False)
suspension_end_time = models.DateTimeField(null=True, blank=True)
suspension_reason = models.TextField(blank=True, null=True)

def suspend_for_24h(self, reason=''):
    self.is_suspended = True
    self.suspension_end_time = timezone.now() + timedelta(hours=24)
    self.suspension_reason = reason
    self.save()
    UserActivityLog.objects.create(user=self.user, action='...', reason=reason)

def disable_permanently(self, reason=''):
    self.is_active = False
    self.user.is_active = False
    self.user.save()
    self.save()
    UserActivityLog.objects.create(user=self.user, action='...', reason=reason)

def enable_user(self, reason=''):
    self.is_active = True
    self.is_suspended = False
    self.suspension_end_time = None
    self.user.is_active = True
    self.user.save()
    self.save()
    UserActivityLog.objects.create(user=self.user, action='...', reason=reason)

def is_currently_suspended(self):
    if self.is_suspended and self.suspension_end_time:
        if timezone.now() < self.suspension_end_time:
            return True
        self.is_suspended = False
        self.suspension_end_time = None
        self.save()
    return False
```

#### 3. Activity Logging Pattern
All user actions are logged:
```python
UserActivityLog.objects.create(
    user=user,
    action='Associate user created with ID: {associate_id}',
    reason=reason,
)
```

#### 4. Many-to-Many Relationships
Multi-tenant company access:
```python
companyid = models.ManyToManyField(Company, related_name='associate_company', blank=True)

def get_companies(self):
    return self.companyid.all()

def add_company(self, company):
    self.companyid.add(company)

def remove_company(self, company):
    self.companyid.remove(company)
```

#### 5. Status Display Methods
Computed status based on multiple flags:
```python
def get_status_display(self):
    if not self.is_active:
        return 'Disabled'
    elif self.is_currently_suspended():
        return 'Suspended'
    return 'Active'
```

#### 6. Computed Properties
Use @property for derived data:
```python
@property
def full_address(self):
    address_parts = [self.address1, self.address2, self.address3, 
                     f"{self.district_id.district_name}, {self.state_id.state_name}", 
                     self.pin]
    return ', '.join(part for part in address_parts if part)
```

### Django View Patterns

#### 1. Decorator-based Authorization
```python
from Sapp.decorators import superadmin_required

@superadmin_required
def dashboard(request):
    # View logic
```

#### 2. Transaction Management
Critical operations wrapped in atomic transactions:
```python
from django.db import transaction

with transaction.atomic():
    user = User.objects.create_user(...)
    associate = associateuser.objects.create(...)
    if company_ids:
        associate.companyid.set(company_objects)
```

#### 3. Error Handling with Rollback
```python
try:
    with transaction.atomic():
        # Create user and related objects
        user = User.objects.create_user(...)
        associate = associateuser.objects.create(...)
    messages.success(request, 'Created successfully!')
    return redirect('list_view')
except Exception as e:
    logger.exception("Error creating: %s", e)
    messages.error(request, f'Error: {e}')
```

#### 4. Password Validation
Always validate passwords using Django's validators:
```python
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

try:
    validate_password(password1, user=user)
    user.set_password(password1)
    user.save()
except ValidationError as ve:
    for error in ve.messages:
        messages.error(request, error)
```

#### 5. Company Context Pattern
Views check for selected company:
```python
def _company_ctx(request):
    """Return selected company or None."""
    cid = request.session.get('selected_company_id')
    if not cid:
        return None
    return Company.objects.filter(company_id=cid).first()

def list_employee(request):
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    employees = employee.objects.filter(CompanyID=company)
    return render(request, 'template.html', {'employees': employees})
```

#### 6. Form Context Helper
Reusable context builder for dropdowns:
```python
def _form_ctx(company):
    """Return dropdowns scoped to selected company."""
    return {
        'designations': designation.objects.filter(company=company, is_active=True),
        'branches': branch.objects.filter(companyid=company),
        'departments': department.objects.filter(companyid=company),
        'states': State.objects.all(),
    }
```

#### 7. Logging Pattern
Structured logging with context:
```python
import logging
logger = logging.getLogger(__name__)

logger.info("Associate created: id='%s' by superadmin='%s'", associate_id, request.user.username)
logger.error("get_districts error for state_id=%s: %s", state_id, e)
logger.exception("Error creating associate: %s", e)
```

#### 8. Message Feedback Pattern
Always provide user feedback:
```python
from django.contrib import messages

messages.success(request, 'Operation completed successfully!')
messages.error(request, 'An error occurred.')
messages.warning(request, 'Please select a company first.')
messages.info(request, 'Information message.')
```

### Django Form Patterns

#### 1. ModelForm with Widgets
Customize form rendering with widgets:
```python
class create_company_form_superadmin(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['company_name', 'start_date', ...]
        widgets = {
            'company_name': forms.TextInput(attrs={'placeholder': 'Company Name'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'email1': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
        }
```

#### 2. Custom Validation Methods
```python
def clean_pan(self):
    pan = self.cleaned_data.get('pan')
    if len(pan) != 10:
        raise forms.ValidationError("PAN number must be exactly 10 characters.")
    return pan
```

#### 3. Nested Form Classes
Forms within forms for related functionality:
```python
class create_company_form_superadmin(forms.ModelForm):
    # Main form
    
    class quick_company_form(forms.Form):
        # Quick create variant
        
    class statuaryForm(forms.ModelForm):
        # Related statutory form
```

### Utility Function Patterns

#### 1. Factory Functions
Create complex objects with validation:
```python
def create_associate_user(username, email, first_name, last_name, password,
                          associate_id, mobile=None, address=None, companies=None):
    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
        )
        associate = associateuser.objects.create(
            user=user,
            associate_id=associate_id,
            mobile=mobile,
            address=address,
        )
        if companies:
            for company in companies:
                associate.add_company(company)
        UserActivityLog.objects.create(
            user=user,
            action=f'Associate user created with ID: {associate_id}',
        )
        return associate
    except Exception as e:
        if 'user' in locals():
            user.delete()
        raise e
```

#### 2. Type Detection Pattern
Determine user type dynamically:
```python
def get_user_type(user):
    if hasattr(user, 'associate_profile'):
        return 'associate', user.associate_profile
    elif hasattr(user, 'subuser_profile'):
        return 'subuser', user.subuser_profile
    elif hasattr(user, 'profile'):
        return 'regular', user.profile
    return 'unknown', None
```

#### 3. Access Control Utility
Centralized access checking:
```python
def can_user_access_system(user):
    """Check whether any type of user is allowed to access the system."""
    user_type, profile = get_user_type(user)
    if user_type == 'associate':
        return profile.can_access_system()
    elif user_type == 'subuser':
        return profile.can_access_system()
    elif user_type == 'regular':
        return profile.can_login() if profile else user.is_active
    return user.is_active
```

### Excel Export/Import Patterns

#### 1. Template Generation
```python
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

wb = openpyxl.Workbook()
ws = wb.active
ws.title = 'Employees'

headers = ['employeecode*', 'name*', 'gender*', ...]
hdr_fill = PatternFill('solid', fgColor='1D3557')
hdr_font = Font(color='FFFFFF', bold=True)

for col, h in enumerate(headers, 1):
    cell = ws.cell(row=1, column=col, value=h)
    cell.fill = hdr_fill
    cell.font = hdr_font
    cell.alignment = Alignment(horizontal='center')
    ws.column_dimensions[cell.column_letter].width = 18
```

#### 2. Bulk Import with Validation
```python
# Build lookup maps
designation_map = {d.designationname: d for d in designation.objects.filter(company=company)}
department_map = {d.department_name: d for d in department.objects.filter(companyid=company)}

created = errors = 0
error_rows = []

for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
    if not any(row):
        continue
    
    # Extract and validate fields
    employeecode = str(row[0]).strip() if row[0] else ''
    
    # Check duplicates
    if employee.objects.filter(employeecode=employeecode, CompanyID=company).exists():
        error_rows.append(f"Row {row_num}: Employee code '{employeecode}' already exists.")
        errors += 1
        continue
    
    # Lookup foreign keys
    desig = designation_map.get(designation_name)
    if not desig:
        error_rows.append(f"Row {row_num}: Designation '{designation_name}' not found.")
        errors += 1
        continue
    
    try:
        employee.objects.create(...)
        created += 1
    except Exception as e:
        error_rows.append(f"Row {row_num}: {e}")
        errors += 1
```

## Best Practices

### Security
1. **Never log passwords**: Use placeholders or omit entirely
2. **Validate password strength**: Use Django's validate_password()
3. **Atomic transactions**: Wrap critical operations in transaction.atomic()
4. **Access control**: Check user permissions before operations
5. **CSRF protection**: Enabled by default, never disable
6. **SQL injection prevention**: Use Django ORM, never raw SQL with user input

### Database
1. **Explicit table names**: Always set db_table in Meta
2. **Explicit column names**: Use db_column for foreign keys
3. **Select related**: Use select_related() for foreign keys to reduce queries
4. **Prefetch related**: Use prefetch_related() for many-to-many
5. **Unique constraints**: Set unique=True or unique_together in Meta
6. **Null vs blank**: null=True for database, blank=True for forms

### Error Handling
1. **Try-except blocks**: Wrap risky operations
2. **Logging**: Log exceptions with logger.exception()
3. **User feedback**: Always provide messages to users
4. **Rollback**: Use transactions to ensure data consistency
5. **Validation**: Validate early, fail fast

### Performance
1. **Query optimization**: Use select_related() and prefetch_related()
2. **Bulk operations**: Use bulk_create() for multiple inserts
3. **Pagination**: Paginate large result sets
4. **Caching**: Cache expensive queries (not implemented yet, but recommended)
5. **Database indexes**: Add indexes for frequently queried fields

### Code Reusability
1. **Helper functions**: Extract common logic into utility functions
2. **Mixins**: Use mixins for shared view behavior
3. **Context processors**: Share data across all templates
4. **Middleware**: Handle cross-cutting concerns
5. **Decorators**: Reuse authorization logic

### Testing (Recommended)
1. **Unit tests**: Test individual functions and methods
2. **Integration tests**: Test view workflows
3. **Model tests**: Test model methods and constraints
4. **Form tests**: Test validation logic
5. **Coverage**: Aim for high test coverage

## Common Idioms

### 1. Get or 404 Pattern
```python
from django.shortcuts import get_object_or_404

company = get_object_or_404(Company, company_id=company_id)
```

### 2. Filter with Exists Check
```python
if User.objects.filter(username=username).exists():
    messages.error(request, 'Username already exists!')
```

### 3. POST Data Extraction
```python
p = request.POST
company_name = p.get('company_name', '')
start_date = p.get('start_date') or None  # For optional dates
is_active = p.get('is_active') == 'True'  # For booleans
```

### 4. Session-based Context
```python
request.session['selected_company_id'] = int(company_id)
company_id = request.session.get('selected_company_id')
```

### 5. Conditional Field Assignment
```python
same = p.get('same_as_permanent') == 'on'
emp.permanentaddress = p['temporaryaddress'] if same else p.get('permanentaddress', '')
```

### 6. List Comprehension for Filtering
```python
company_ids = [c for c in request.POST.getlist('companies') if c]
```

### 7. Values List for IDs
```python
company_ids = associate.companyid.values_list('company_id', flat=True)
```

### 8. JSON Response Pattern
```python
from django.http import JsonResponse

return JsonResponse({'companies': list(companies), 'selected_id': selected_id})
return JsonResponse({'error': 'Unable to fetch data.'}, status=500)
```

## Annotations and Decorators

### Custom Decorators
```python
# Sapp/decorators.py
from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

def superadmin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_superuser:
            return HttpResponseForbidden("Access denied")
        return view_func(request, *args, **kwargs)
    return wrapper
```

### Django Built-in Decorators
```python
from django.contrib.auth.decorators import login_required

@login_required
def view_function(request):
    # View logic
```

## Internal API Usage

### User Creation
```python
from django.contrib.auth.models import User

user = User.objects.create_user(
    username=username,
    email=email,
    first_name=first_name,
    last_name=last_name,
    password=password,
)
```

### Password Management
```python
user.set_password(new_password)
user.save()
```

### Authentication
```python
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout

user = authenticate(username=username, password=password)
if user:
    auth_login(request, user)
```

### Timezone Handling
```python
from django.utils import timezone
from datetime import timedelta

now = timezone.now()
future = timezone.now() + timedelta(hours=24)
```

### Messages Framework
```python
from django.contrib import messages

messages.success(request, 'Success message')
messages.error(request, 'Error message')
messages.warning(request, 'Warning message')
messages.info(request, 'Info message')
```

### Query Optimization
```python
# Select related (foreign keys)
employees = employee.objects.filter(CompanyID=company).select_related(
    'designationID', 'branchID', 'departmentID'
)

# Prefetch related (many-to-many)
associates = associateuser.objects.all().select_related('user')
```

## Code Style Preferences

1. **String Formatting**: Use f-strings for readability
   ```python
   messages.success(request, f'Associate {associate.associate_id} created successfully!')
   ```

2. **Conditional Expressions**: Use ternary operators for simple conditions
   ```python
   value = default_value if condition else other_value
   ```

3. **Dictionary Comprehensions**: For building lookup maps
   ```python
   designation_map = {d.designationname: d for d in designation.objects.filter(...)}
   ```

4. **Explicit is Better**: Always be explicit about None, True, False
   ```python
   if value is None:
   if flag is True:
   ```

5. **Early Returns**: Fail fast, return early
   ```python
   if not company:
       messages.warning(request, 'Please select a company first.')
       return redirect('dashboard')
   ```
