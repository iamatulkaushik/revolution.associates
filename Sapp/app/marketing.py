"""
Public marketing pages: Features, Pricing, Compliance, About, Contact.
Static content, no login required. SEO-focused for organic + AI-index discovery.
"""

from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponse


def features(request):
    return render(request, 'marketing/features.html')


def pricing(request):
    return render(request, 'marketing/pricing.html')


def compliance(request):
    return render(request, 'marketing/compliance.html')


def about(request):
    return render(request, 'marketing/about.html')


def contact(request):
    return render(request, 'marketing/contact.html')


def contact_submit(request):
    if request.method != 'POST':
        return redirect('contact')

    name = request.POST.get('name', '').strip()
    company = request.POST.get('company', '').strip()
    email = request.POST.get('email', '').strip()
    phone = request.POST.get('phone', '').strip()
    message = request.POST.get('message', '').strip()

    if not (name and company and email and message):
        messages.error(request, "Please fill all required fields.")
        return redirect('contact')

    body = f"Name: {name}\nCompany: {company}\nEmail: {email}\nPhone: {phone}\n\n{message}"
    send_mail(
        subject=f"New demo request — {company}",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.DEFAULT_FROM_EMAIL],
        fail_silently=True,
    )
    messages.success(request, "Thanks — we'll be in touch within one business day.")
    return redirect('contact')


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Sitemap: https://reas.host/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml(request):
    pages = [
        ("https://reas.host/", "1.0"),
        ("https://reas.host/features/", "0.9"),
        ("https://reas.host/pricing/", "0.9"),
        ("https://reas.host/compliance/", "0.9"),
        ("https://reas.host/about/", "0.7"),
        ("https://reas.host/contact/", "0.7"),
    ]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, priority in pages:
        xml.append(f"  <url><loc>{url}</loc><priority>{priority}</priority></url>")
    xml.append('</urlset>')
    return HttpResponse("\n".join(xml), content_type="application/xml")
