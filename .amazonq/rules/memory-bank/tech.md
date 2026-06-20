# Technology Stack

## Programming Languages
- **Python**: Primary language (Django 6.0.1 compatible, Python 3.10+)
- **HTML/CSS**: Frontend templates
- **JavaScript**: Client-side interactions

## Core Framework
- **Django 6.0.1**: Web framework
- **django-hosts**: Subdomain routing and multi-tenant support

## Database
- **SQLite3**: Default development database (db.sqlite3)
- **PostgreSQL/MySQL**: Production-ready (configurable via environment variables)
- **Database Configuration**:
  - Engine: `DB_ENGINE` (default: django.db.backends.sqlite3)
  - Name: `DB_NAME`
  - User: `DB_USER`
  - Password: `DB_PASSWORD`
  - Host: `DB_HOST`
  - Port: `DB_PORT`

## Development Tools
- **livereload**: Auto-reload during development
- **Django Admin**: Built-in admin interface
- **Django Debug Toolbar**: (implied for development)

## Security
- **Django Auth**: Built-in authentication system
- **Password Validation**: 8+ character minimum, complexity checks
- **CSRF Protection**: Enabled by default
- **Session Management**: Cookie-based sessions
- **Production Headers**:
  - SECURE_BROWSER_XSS_FILTER
  - SECURE_CONTENT_TYPE_NOSNIFF
  - X_FRAME_OPTIONS = 'DENY'
  - SESSION_COOKIE_SECURE
  - CSRF_COOKIE_SECURE
  - HSTS (31536000 seconds)

## Logging
- **Python logging module**: Structured logging
- **RotatingFileHandler**: Log rotation (5MB/10MB limits)
- **Log Files**:
  - logs/errors.log (ERROR level, 5MB, 5 backups)
  - logs/app.log (INFO level, 10MB, 5 backups)
- **Formatters**: Verbose (timestamp, level, module, line) and simple

## Static Files
- **Static URL**: /static/
- **Static Root**: static_collected/ (for production collectstatic)
- **Media URL**: /media/
- **Media Root**: media/

## Environment Configuration
- **.env file**: Environment variables
- **Key Variables**:
  - DJANGO_SECRET_KEY
  - DJANGO_DEBUG (True/False)
  - DJANGO_ALLOWED_HOSTS (comma-separated)
  - DJANGO_PARENT_HOST (default: localhost:8000)
  - DB_ENGINE, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT

## Internationalization
- **Language**: en-us
- **Timezone**: Asia/Kolkata
- **USE_I18N**: True
- **USE_TZ**: True

## Development Commands

### Setup
```bash
# Install dependencies (create requirements.txt from imports)
pip install django==6.0.1 django-hosts

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files (production)
python manage.py collectstatic
```

### Running the Server
```bash
# Development server
python manage.py runserver

# Access points:
# - http://localhost:8000 (main site)
# - http://aapp.localhost:8000 (associate panel)
```

### Database Management
```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Database shell
python manage.py dbshell
```

### Testing
```bash
# Run tests
python manage.py test

# Run specific app tests
python manage.py test Sapp
python manage.py test Aapp
```

### Utilities
```bash
# Django shell
python manage.py shell

# Check for issues
python manage.py check

# Show migrations
python manage.py showmigrations
```

## Project Dependencies (Inferred)
```
Django==6.0.1
django-hosts
```

## Deployment Considerations

### Production Settings
- Set `DEBUG=False` in .env
- Configure `DJANGO_SECRET_KEY` (strong random key)
- Set `DJANGO_ALLOWED_HOSTS` to actual domains
- Use PostgreSQL or MySQL instead of SQLite
- Enable all security headers (auto-enabled when DEBUG=False)
- Configure HTTPS for secure cookies

### Database Migration
```bash
# Export from SQLite (development)
python manage.py dumpdata > data.json

# Import to production database
python manage.py loaddata data.json
```

### Static Files
```bash
# Collect static files for production
python manage.py collectstatic --noinput
```

### Logging
- Ensure logs/ directory exists and is writable
- Configure log rotation in production (handled by RotatingFileHandler)
- Monitor logs/errors.log for critical issues

## Architecture Notes

### Multi-tenant Subdomain Setup
- Requires DNS/hosts file configuration for subdomains
- Development: Add to hosts file (127.0.0.1 aapp.localhost)
- Production: Configure DNS A records for subdomains

### Middleware Order (Critical)
1. django_hosts.middleware.HostsRequestMiddleware (first)
2. SecurityMiddleware
3. SessionMiddleware
4. CommonMiddleware
5. CsrfViewMiddleware
6. AuthenticationMiddleware
7. Aapp.middleware.CompanyMiddleware (custom)
8. MessageMiddleware
9. ClickjackingMiddleware
10. django_hosts.middleware.HostsResponseMiddleware (last)

### Template Context Processors
- django.template.context_processors.request
- django.contrib.auth.context_processors.auth
- django.contrib.messages.context_processors.messages
- Aapp.context_processors.company_context (custom)

## File Upload Configuration
- **MEDIA_URL**: /media/
- **MEDIA_ROOT**: BASE_DIR / "media"
- Used for employee documents, company logos, etc.

## Default Settings
- **DEFAULT_AUTO_FIELD**: BigAutoField (64-bit primary keys)
- **ROOT_HOSTCONF**: revolution.hosts
- **DEFAULT_HOST**: www
- **PARENT_HOST**: localhost:8000 (development)
