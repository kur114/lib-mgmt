from django.apps import AppConfig


class LibMgmtConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lib_mgmt'
    templatetags = 'lib_mgmt.templatetags'