# Project Structure

## Directory Organization

```
revolution.associates/
├── revolution/          # Django project configuration
│   ├── settings.py     # Main settings with environment-based config
│   ├── urls.py         # Root URL configuration
│   ├── hosts.py        # Subdomain routing (www, aapp)
│   ├── wsgi.py         # WSGI application entry point
│   └── asgi.py         # ASGI application entry point
│
├── Sapp/               # Superadmin application
│   ├── app/            # Modular business logic
│   │   ├── bank.py
│   │   ├── company.py
│   │   ├── license.py
│   │   ├── state_district.py
│   │   └── user.py
│   ├── migrations/     # Database migrations
│   ├── models.py       # Data models (imports from app/)
│   ├── views.py        # View controllers
│   ├── urls.py         # URL routing
│   ├── forms.py        # Form definitions
│   ├── decorators.py   # Custom decorators (@superadmin_required)
│   └── admin.py        # Django admin configuration
│
├── Aapp/               # Associate application
│   ├── app/            # Modular business logic
│   │   ├── attandance.py
│   │   ├── bonus.py
│   │   ├── branch_department.py
│   │   ├── contractor.py
│   │   ├── designation.py
│   │   ├── employee.py
│   │   ├── gratuity.py
│   │   ├── leave_management.py
│   │   ├── maternity.py
│   │   ├── shops_act.py
│   │   ├── subuser.py
│   │   └── wages.py
│   ├── migrations/     # Database migrations
│   ├── models.py       # Data models (imports from app/)
│   ├── views.py        # View controllers
│   ├── urls.py         # URL routing
│   ├── middleware.py   # CompanyMiddleware for context
│   ├── mixins.py       # Reusable view mixins
│   ├── context_processors.py  # Template context processors
│   └── admin.py        # Django admin configuration
│
├── templates/          # HTML templates
│   ├── Sapp/           # Superadmin templates
│   │   ├── company/    # Company management templates
│   │   ├── license/    # License management templates
│   │   ├── users/      # User management templates
│   │   ├── base.html   # Base template for Sapp
│   │   └── dashboard.html
│   ├── Aapp/           # Associate templates
│   │   ├── attendance/
│   │   ├── company/
│   │   ├── employees/
│   │   ├── users/
│   │   ├── works/
│   │   ├── base.html   # Base template for Aapp
│   │   ├── dashboard.html
│   │   └── navbar.html
│   ├── home.html       # Public homepage
│   ├── login.html      # Superadmin login
│   ├── associate_login.html  # Associate login
│   └── signup.html
│
├── static/             # Static assets
│   ├── css/
│   │   ├── base.css
│   │   └── icons.css
│   ├── fonts/
│   │   ├── Infinitude.ttf
│   │   └── Ubuntu-R.ttf
│   └── favicon.ico
│
├── logs/               # Application logs
│   ├── app.log         # General application logs
│   └── errors.log      # Error-level logs
│
├── .env                # Environment variables (not in version control)
├── .gitignore
├── manage.py           # Django management script
├── db.sqlite3          # SQLite database (development)
└── readme.md
```

## Core Components

### 1. Multi-tenant Routing (django-hosts)
- **revolution/hosts.py**: Defines subdomain patterns
  - `www` → Main site (revolution.urls)
  - `aapp` → Associate panel (Aapp.urls)
  - Default → Falls back to main site
- **Middleware**: HostsRequestMiddleware and HostsResponseMiddleware handle subdomain routing

### 2. Application Architecture

#### Sapp (Superadmin Application)
- **Purpose**: Platform administration, company/license/user management
- **Access**: Restricted to superusers only
- **Key Models**: Company, License, UserProfile, associateuser, SubUser
- **Modular Design**: Business logic separated into app/ modules

#### Aapp (Associate Application)
- **Purpose**: HR operations, employee management, payroll
- **Access**: Associates, sub-users, employees (role-based)
- **Key Models**: Employee, Branch, Department, Designation, Attendance, Leave
- **Middleware**: CompanyMiddleware injects company context into requests

### 3. User Hierarchy
```
Superadmin (Django superuser)
    └── Associate (associateuser)
        └── Sub User (SubUser)
            ├── Owner (full company access)
            ├── Operator (limited HR access)
            └── Employee (view-only)
```

### 4. Database Models

#### Sapp Models (from app/ modules)
- **Company**: Multi-tenant company records (PAN, GST, state, district)
- **License**: License keys with expiry, type, max_users
- **associateuser**: Associates linked to multiple companies
- **SubUser**: Role-based users under associates
- **UserProfile**: Extended user profile data
- **State/District**: Geographic data for company locations
- **Bank**: Bank master data

#### Aapp Models (from app/ modules)
- **Employee**: Employee records with employment type, documents
- **Branch/Department**: Organizational structure
- **Designation**: Job titles and hierarchy
- **Attendance**: Daily attendance with salary year/month
- **Leave**: Leave management
- **Bonus/Gratuity/Wages**: Compensation components
- **Contractor**: Contractor management
- **Maternity/ShopsAct**: Statutory compliance

### 5. Middleware & Context Processors

#### Aapp.middleware.CompanyMiddleware
- Injects company context into requests
- Ensures users only access their assigned companies

#### Aapp.context_processors.company_context
- Provides company data to all templates
- Enables company-aware template rendering

### 6. Security Layers

#### Decorators
- **@superadmin_required**: Restricts views to superusers
- **@login_required**: Standard Django authentication
- Custom role-based decorators in Sapp.decorators

#### Permission System
- **ROLE_PERMISSIONS**: Dictionary defining permissions per role
- Granular permissions: view, add, change, delete
- Module-level permissions: company, employees, attendance, reports, etc.

### 7. Logging Infrastructure
- **Structured Logging**: Separate handlers for errors and info
- **Rotating File Handlers**: 5MB/10MB limits with 5 backups
- **Logger Hierarchy**: 
  - Root logger: WARNING level
  - Django logger: INFO/WARNING based on DEBUG
  - Sapp/Aapp loggers: DEBUG/INFO based on DEBUG

## Architectural Patterns

### 1. Modular Business Logic
- Models split into app/ modules for maintainability
- Each module handles a specific domain (user, company, license, employee, etc.)
- Main models.py imports from app/ modules

### 2. Multi-tenant Data Isolation
- Company-based data segregation
- Many-to-many relationships: Associate ↔ Company, SubUser ↔ Company
- Middleware enforces company context

### 3. Environment-based Configuration
- .env file for sensitive settings
- Fallback defaults for development
- Production security headers enabled when DEBUG=False

### 4. Template Inheritance
- Base templates per application (Sapp/base.html, Aapp/base.html)
- Shared components (navbar, dashboard)
- DRY principle for UI consistency

### 5. Transaction Management
- Atomic transactions for critical operations (user creation, updates)
- Rollback on errors to maintain data integrity

### 6. Separation of Concerns
- Views handle HTTP logic
- Models handle data logic
- Forms handle validation
- Decorators handle authorization
- Middleware handles cross-cutting concerns
