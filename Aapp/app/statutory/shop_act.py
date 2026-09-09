"""
Aapp/app/statutory/shop_act.py
================================
Shops and Commercial Establishments Act — statutory registers
(not yet implemented).

Planned reports:
  - Register of employment
  - Weekly holiday register
  - Working hours / overtime register (per state Shop Act rules)

Follow the same pattern as wages_act.py: pure presentation via
Aapp.app.pdf_engine, aggregation helpers from Aapp.app.statutory.common,
one function per report, returning PDF bytes from build_pdf().
"""
