from django.apps import AppConfig


class RentalNeedsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rental_needs"

    def ready(self):
        import rental_needs.signals