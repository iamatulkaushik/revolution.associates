# Product Overview

## Project Purpose
Revolution Associates is a multi-tenant HR and workforce management platform built with Django. It provides comprehensive employee lifecycle management, attendance tracking, payroll processing, and license-based access control for multiple companies and their associates.

## Value Proposition
- **Multi-tenant Architecture**: Supports multiple companies with isolated data and subdomain-based routing
- **Role-based Access Control**: Hierarchical user system (superadmin → owner → associate → operator → employee)
- **License Management**: Flexible licensing system with suspension, revocation, and expiry tracking
- **Comprehensive HR Features**: Employee management, attendance, leave, payroll, allowances, deductions, and statutory compliance

## Key Features

### User Management
- **Superadmin Panel**: Complete system control, company creation, associate/subuser management
- **Associate Users**: Company-specific access with multi-company support
- **Sub Users**: Role-based users (owner, operator, employee) under associates
- **Account Controls**: 24-hour suspension, permanent disable, password reset, activity logging

### Company Management
- Multi-company registration with PAN, GST, state/district tracking
- Company shut date management
- Quick company creation workflow
- Company-associate relationship mapping

### License System
- License key generation and assignment
- License types: trial, standard, premium, enterprise
- Max user limits per license
- Expiry tracking and renewal
- Suspend/revoke/activate license actions
- Associate-company license binding

### Employee Management (Aapp)
- Complete employee lifecycle (onboarding to exit)
- Employment types: permanent, contract, internship
- Branch and department organization
- Designation hierarchy
- Document tracking (Aadhaar, PAN, driving license, etc.)
- Bank account details

### Attendance & Leave
- Daily attendance recording with salary year/month tracking
- Leave management system
- Maternity leave tracking
- Shops Act compliance

### Payroll & Compensation
- Wage calculation and processing
- Bonus management
- Gratuity calculations
- Allowances and deductions
- Contractor payments

### Security & Compliance
- Password validation (8+ chars, complexity requirements)
- CSRF protection
- Session management
- Structured logging (errors.log, app.log)
- Production security headers (HSTS, XSS filter, content type nosniff)

## Target Users

### Superadmins
- System administrators managing the entire platform
- Create and manage companies, associates, licenses
- Full access to all features and data

### Associates
- HR consultants or service providers managing multiple client companies
- Access to assigned companies only
- Can create sub-users with delegated permissions

### Company Owners
- Business owners managing their own company data
- Full access to their company's employees, attendance, payroll
- Cannot manage other companies

### Operators
- HR staff with limited permissions
- Can manage employees, attendance, allowances, deductions
- View-only access to reports

### Employees
- End users viewing their own data
- Access to personal attendance, salary slips, leave records

## Use Cases

1. **HR Consulting Firms**: Manage multiple client companies from a single platform
2. **Multi-branch Organizations**: Centralized HR management across branches
3. **Payroll Service Providers**: Process payroll for multiple companies with license-based access
4. **SME HR Management**: Small/medium businesses managing their workforce
5. **Compliance Tracking**: Statutory compliance for Shops Act, maternity, gratuity
