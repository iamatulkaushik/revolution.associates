# Factory Module Field Mapping Reference

## FactoryRegistration Model

### Required Fields (from specification)
| Specification Field | Model Field | Type | Description |
|---------------------|-------------|------|-------------|
| factory_license_no | license_number | CharField(100) | Factory license number (unique) |
| occupier_name | occupier_name | CharField(255) | Name of factory occupier |
| manager_name | manager_name | CharField(255) | Name of factory manager |
| factory_area_sqm | factory_area_sqm | DecimalField(10,2) | Factory area in square meters |
| total_hp_used | total_hp_used | DecimalField(10,2) | Total horsepower used |
| max_workers_day | max_workers_day | IntegerField | Maximum workers in day shift |
| max_workers_night | max_workers_night | IntegerField | Maximum workers in night shift |
| license_expiry_date | license_expiry_date | DateField | License expiry date |

### Additional Fields
- factory_name (CharField)
- factory_address (TextField)
- license_issue_date (DateField)
- factory_type (CharField with choices)
- manufacturing_process (TextField)
- max_workers (IntegerField)
- manager_contact (CharField)
- power_used (BooleanField)
- is_active (BooleanField)
- company (ForeignKey to Company)

---

## AccidentRecord Model

### Required Fields (from specification)
| Specification Field | Model Field | Type | Description |
|---------------------|-------------|------|-------------|
| accident_date | accident_date | DateTimeField | Date and time of accident |
| nature_of_accident | nature_of_accident | CharField(255) | Nature/type of accident |
| injury_description | injury_description | TextField | Description of injuries |
| is_fatal | is_fatal | BooleanField | Whether accident was fatal |
| days_lost | days_lost | IntegerField | Working days lost due to accident |
| reported_to_dish | reported_to_dish | BooleanField | Reported to DISH (Directorate of Industrial Safety and Health) |
| dish_reference_no | dish_reference_no | CharField(100) | DISH reference number |

### Additional Fields
- factory (ForeignKey to FactoryRegistration)
- employee (ForeignKey to employee, optional)
- location (CharField)
- description (TextField)
- severity (CharField with choices: minor, major, fatal)
- injury_details (TextField)
- immediate_action (TextField)
- reported_to_authority (BooleanField)
- authority_report_date (DateField)
- compensation_paid (DecimalField)
- preventive_measures (TextField)

---

## AnnualReturn Model

### Required Fields (from specification)
| Specification Field | Model Field | Type | Description |
|---------------------|-------------|------|-------------|
| total_workers_male | total_workers_male | IntegerField | Total male workers |
| total_workers_female | total_workers_female | IntegerField | Total female workers |
| total_man_days | total_man_days | IntegerField | Total man-days worked |
| total_overtime_hours | total_overtime_hours | DecimalField(10,2) | Total overtime hours |
| total_accidents | total_accidents | IntegerField | Total accidents in year |
| total_wages_paid | total_wages_paid | DecimalField(15,2) | Total wages paid |
| filing_status | filing_status | CharField | Filing status (draft/submitted/acknowledged) |
| acknowledgement_no | acknowledgement_no | CharField(100) | Acknowledgement number |

### Additional Fields
- factory (ForeignKey to FactoryRegistration)
- year (IntegerField)
- total_workers (IntegerField)
- male_workers (IntegerField)
- female_workers (IntegerField)
- child_workers (IntegerField)
- total_working_days (IntegerField)
- accidents_reported (IntegerField)
- leave_with_wages (IntegerField)
- overtime_worked (DecimalField)
- submitted_date (DateField)
- submitted_by (CharField)
- remarks (TextField)

---

## WhitewashRegister Model (NEW)

### Required Fields (from specification)
| Specification Field | Model Field | Type | Description |
|---------------------|-------------|------|-------------|
| area_description | area_description | CharField(255) | Description of area whitewashed |
| type_of_work | type_of_work | CharField(50) | Type of work (whitewash/painting/varnish/cleaning) |
| date_done | date_done | DateField | Date work was completed |
| next_due_date | next_due_date | DateField | Next due date for work |
| contractor_name | contractor_name | CharField(255) | Name of contractor |

### Additional Fields
- factory (ForeignKey to FactoryRegistration)
- remarks (TextField)
- created_at (DateTimeField)
- updated_at (DateTimeField)

---

## VesselExamination Model (NEW)

### Required Fields (from specification)
| Specification Field | Model Field | Type | Description |
|---------------------|-------------|------|-------------|
| vessel_description | vessel_description | CharField(255) | Description of vessel |
| exam_date | exam_date | DateField | Examination date |
| examiner_name | examiner_name | CharField(255) | Name of examiner |
| max_permissible_pressure | max_permissible_pressure | DecimalField(10,2) | Maximum pressure (PSI/Bar) |
| is_fit_for_use | is_fit_for_use | BooleanField | Whether vessel is fit for use |

### Additional Fields
- factory (ForeignKey to FactoryRegistration)
- vessel_identification (CharField)
- examiner_qualification (CharField)
- defects_found (TextField)
- recommendations (TextField)
- next_exam_date (DateField)
- certificate_number (CharField)
- created_at (DateTimeField)
- updated_at (DateTimeField)

---

## LeaveWithWagesRegister Model (NEW)

### Required Fields (from specification)
| Specification Field | Model Field | Type | Description |
|---------------------|-------------|------|-------------|
| opening_balance | opening_balance | DecimalField(5,2) | Opening leave balance |
| leave_earned | leave_earned | DecimalField(5,2) | Leave earned in period |
| leave_availed | leave_availed | DecimalField(5,2) | Leave taken |
| leave_lapsed | leave_lapsed | DecimalField(5,2) | Leave lapsed |
| leave_encashed | leave_encashed | DecimalField(5,2) | Leave encashed |
| encashment_amount | encashment_amount | DecimalField(10,2) | Encashment amount paid |

### Additional Fields
- employee (ForeignKey to employee)
- factory (ForeignKey to FactoryRegistration)
- year (IntegerField)
- closing_balance (DecimalField) - Auto-calculated
- remarks (TextField)
- created_at (DateTimeField)
- updated_at (DateTimeField)

### Calculation Method
```python
closing_balance = opening_balance + leave_earned - leave_availed - leave_lapsed - leave_encashed
```

---

## Form Field Widgets

### Common Widgets Used
- **TextInput**: Single-line text fields (names, numbers, IDs)
- **Textarea**: Multi-line text (descriptions, remarks, addresses)
- **DateInput**: Date fields with type='date'
- **DateTimeInput**: DateTime fields with type='datetime-local'
- **NumberInput**: Numeric fields with step attribute for decimals
- **Select**: Dropdown choices (factory_type, severity, filing_status, type_of_work)
- **CheckboxInput**: Boolean fields (is_fatal, is_fit_for_use, power_used)

### Bootstrap Classes
All form fields use `class='form-control'` for consistent styling
Checkboxes use `class='form-check-input'`

---

## URL Patterns

### Factory Registration
- List: `/factory/registration/`
- Create: `/factory/registration/create/`
- Update: `/factory/registration/update/<id>/`

### Accident Records
- List: `/factory/accident/`
- Create: `/factory/accident/create/`

### Annual Returns
- List: `/factory/annual-return/`
- Create: `/factory/annual-return/create/`

### Whitewash Register
- List: `/factory/whitewash/`
- Create: `/factory/whitewash/create/`

### Vessel Examination
- List: `/factory/vessel/`
- Create: `/factory/vessel/create/`

### Leave with Wages Register
- List: `/factory/leave-wages/`
- Create: `/factory/leave-wages/create/`

### Dashboard
- Dashboard: `/factory/dashboard/`

---

## View Functions

### Pattern
All views follow the same pattern:
1. Check company context (`_company_ctx(request)`)
2. Redirect to dashboard if no company selected
3. GET: Render form with context
4. POST: Validate and save data
5. Success: Redirect to list view with success message
6. Error: Log exception and show error message

### Common Context Variables
- `company`: Selected company object
- `factories`: List of active factories for dropdown
- `employees`: List of employees for dropdown
- Form-specific data lists

---

## Database Migrations Required

After implementing these changes, run:
```bash
python manage.py makemigrations Aapp
python manage.py migrate
```

This will create/update the following tables:
1. factory_registration (UPDATE)
2. factory_accident_record (UPDATE)
3. factory_annual_return (UPDATE)
4. factory_whitewash_register (NEW)
5. factory_vessel_examination (NEW)
6. factory_leave_with_wages_register (NEW)
