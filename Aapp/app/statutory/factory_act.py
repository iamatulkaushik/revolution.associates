"""
Aapp/app/statutory/factory_act.py
===================================
Factory Act, 1948 — statutory registers (not yet implemented).

Planned reports:
  - Form 25 (Register of Adult Workers)
  - Form 20 (Muster Roll)
  - Overtime register
  - Leave with Wages register (Form 15/16)

Follow the same pattern as wages_act.py: pure presentation via
Aapp.app.pdf_engine, aggregation helpers from Aapp.app.statutory.common,
one function per report, returning PDF bytes from build_pdf().
"""
