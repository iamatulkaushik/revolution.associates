#!/usr/bin/env bash
# Merge gate for the Capp upgrade (docs/capp_upgrade/01_COMMON_RULES.md section 5).
# Run from the repo root. Stops at the first failure.
set -euo pipefail
echo "1/6 py_compile";        python -m py_compile $(git ls-files '*.py')
echo "2/6 manage.py check";   python manage.py check
echo "3/6 makemigrations";    python manage.py makemigrations --check --dry-run
echo "4/6 duplicate URL names (only capp_login is a known alias)"
dups=$(grep -oP "name='\K[^']+" Capp/urls.py Capp/*/urls.py | sed 's/^[^:]*://' | sort | uniq -d | grep -vx capp_login || true)
if [ -n "$dups" ]; then echo "DUPLICATE URL NAMES:"; echo "$dups"; exit 1; fi
echo "5/6 migrate --plan";    python manage.py migrate --plan | tail -5
echo "6/6 tests";             python manage.py test Capp
echo "GATE PASSED"
