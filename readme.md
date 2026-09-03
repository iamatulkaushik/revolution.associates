# Revolution Associates HRMS

Revolution Associates is a Django-based Human Resource Management System (HRMS) designed to support employee management, payroll operations, attendance tracking, and statutory compliance for businesses. The project is organized around multiple application modules for associates, companies, and admin users and supports a multi-host architecture through Django Hosts.

## Overview

This system is built to help organizations manage:

- Employee records and workforce lifecycle
- Attendance, shift, and punch log tracking
- Salary processing and payroll workflows
- Leave and overtime management
- Compliance returns and regulatory reporting
- Loans, advances, expense claims, and benefits
- Company and associate administration

It is intended as a business-focused HR and payroll platform for managing internal operations efficiently while reducing manual work and improving reporting accuracy.

## Features

### Employee and Workforce Management
- Employee creation, update, disable, retirement, and deletion
- Designation and department management
- Bulk employee upload using Excel templates
- Employee banking, statutory, KYC, and nominee details
- Branch and company-level workforce records
- Subuser access management

### Attendance and Shift Management
- Attendance tracking and updates
- Bulk attendance upload
- Punch log ingestion and processing
- Biometric device support
- Shift creation and assignment
- Overtime register management
- Daily attendance view and reporting

### Leave and Employee Operations
- Leave records and updates
- Leave approval workflows
- Absence and workforce tracking

### Payroll and Salary Processing
- Salary structure definitions
- Salary batch creation and processing
- Salary slip generation
- Payroll approval and reprocessing
- Export of salary registers and bank advice files
- PF and ESI-related payroll reports

### Compliance and Statutory Reporting
- EPF and ESI nomination and filing support
- ECR and return tracking
- Bonus and gratuity management
- Factory Act, Shops Act, and labour welfare tracking
- Minimum Wages and Payment of Wages compliance
- Compliance calendar and tracker
- Labour returns and statutory filing workflows

### Finance and Benefits
- Loan and advance management
- Loan schedule generation
- Arrear tracking and schedule generation
- Expense claim management and approval flow

### Reporting and Document Generation
- PDF generation for salary slips and registers
- Report exports for payroll, bank files, and compliance
- Bulk data import/export using Excel templates
- Dashboard metrics and workforce overview

### Security and Access Control
- Role-based access control
- Company and associate-specific scoping
- Admin and subuser permission management
- Secure data separation between hosted application areas

## Project Structure

```text
revolution.associates/
├── Aapp/                     # Associate-facing HR and payroll modules
├── Capp/                    # Company-focused app scaffold
├── Cxapp/                   # Company portal / workforce management app
├── Sapp/                    # Superuser/admin and licensing management
├── revolution/              # Django project settings and routing
├── templates/               # HTML templates
├── static/                  # CSS, fonts, and static assets
├── media/                   # Uploaded media files
├── logs/                    # Application logs
├── manage.py                # Django command entry point
├── requirements.txt         # Python dependencies
├── readme.md                # Project documentation
├── db.sqlite3               # Local database for development
├── whole_project.md         # Additional project overview
└── render.yaml              # Deployment configuration
```

## Technology Stack

- Python 3.x
- Django 6.0.1
- django-hosts
- SQLite (default local DB)
- HTML / Django templates
- CSS / static assets
- OpenPyXL for Excel-based import/export
- Gunicorn for production hosting

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/revolution.associates.git
cd revolution.associates
```

### 2. Create and activate a virtual environment

On Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Apply migrations

```bash
python manage.py migrate
```

### 5. Create an admin user

```bash
python manage.py createsuperuser
```

### 6. Run the development server

```bash
python manage.py runserver
```

Open the application in your browser at:

```text
http://127.0.0.1:8000/
```

## Host / Routing Notes

The project uses Django Hosts to separate application behavior by host or domain, including modules for:

- Main frontend and general routes
- Associate portal
- Company portal
- Admin interface

This setup allows different user flows to be separated based on domain or host configuration in the Django project.

## Environment Configuration

The project includes support for environment-based configuration and optional `.env` usage, depending on the deployment setup. It is designed to support both local development and hosted deployments.

## Usage Scenarios

This project is suitable for:

- HR departments managing employee data and records
- Payroll teams processing monthly salary batches
- Compliance teams tracking legal deadlines and statutory returns
- Companies handling attendance, payroll, and labour reporting
- Admin users managing licenses, users, and company-level controls

## Security Considerations

The application includes a structured access model with separation between:

- admin users
- associate users
- company users
- sub-users / role-specific workflows

This helps keep sensitive payroll and compliance data protected and organized by business role.

## Contributing

Contributions are welcome. To contribute:

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to your branch
5. Open a pull request

## License

This project does not currently include a dedicated license file in the repository root. Please confirm licensing terms with the project owner before public distribution or commercial use.

## Contact

For project ownership, collaboration, or deployment support, contact the repository maintainer or project admin.

## Notes

This project is actively structured around HR, payroll, and compliance workflows and is best viewed as a business software platform rather than a generic starter app. The codebase includes a broad set of operational modules for human resource and statutory management.
