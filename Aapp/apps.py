from django.apps import AppConfig


class AappConfig(AppConfig):
    name = 'Aapp'

    def ready(self):
        from Aapp.app.shops_act import connect_primary_establishment_signal
        connect_primary_establishment_signal()