from django.apps import AppConfig


class SappConfig(AppConfig):
    name = 'Sapp'

    def ready(self):
        from Sapp.app.audit_trail import connect_audit_signals
        connect_audit_signals()
