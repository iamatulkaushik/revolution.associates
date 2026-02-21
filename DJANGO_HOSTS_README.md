# Django Hosts Subdomain Configuration

## Setup Complete

Your application is now configured to use django-hosts for subdomain routing.

## Configuration

- **Main App (Sapp)**: Accessible at `http://localhost:8000` or `http://www.localhost:8000`
- **Associate App (Aapp)**: Accessible at `http://aapp.localhost:8000`

## How to Access

1. Start the development server:
   ```
   python manage.py runserver
   ```

2. Access the applications:
   - Main application: http://localhost:8000 or http://www.localhost:8000
   - Associate subdomain: http://aapp.localhost:8000

## Routes

### Main App (Sapp)
- Dashboard: http://localhost:8000/dashboard/
- Login: http://localhost:8000/signin/
- Companies: http://localhost:8000/company/list/
- Associates: http://localhost:8000/users/associate/list/
- Licenses: http://localhost:8000/license/list/

### Associate App (Aapp)
- Home: http://aapp.localhost:8000/
- Login: http://aapp.localhost:8000/login/
- Profile: http://aapp.localhost:8000/profile/

## Files Modified/Created

1. `revolution/settings.py` - Added django-hosts configuration
2. `revolution/hosts.py` - Created host patterns
3. `Aapp/urls.py` - Updated URL patterns for subdomain

## Notes

- The subdomain routing works automatically in development
- For production, configure your web server (nginx/apache) to handle subdomains
- Update ALLOWED_HOSTS in production with your actual domain
