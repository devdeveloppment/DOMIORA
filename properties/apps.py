from django.apps import AppConfig


class PropertiesConfig(AppConfig):
    name = 'properties'

    def ready(self):
        from .video import checks  # noqa: F401  (enregistre les contrôles de production)
