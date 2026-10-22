import os

from django.conf import settings

from site_settings.models import SiteSettings

_CSS_FILES = ("css/tailwind.css", "css/design-system.css")


def _asset_version():
    """
    En local (DEBUG), les fichiers statiques n'ont pas d'empreinte dans leur nom : sans ce numéro de version,
    le navigateur peut garder un ancien CSS après une mise à jour. En production, le stockage « Manifest »
    donne déjà un nom unique à chaque version : rien à ajouter.
    """
    if not settings.DEBUG:
        return ""
    stamps = []
    for name in _CSS_FILES:
        for folder in settings.STATICFILES_DIRS:
            try:
                stamps.append(int(os.path.getmtime(os.path.join(folder, name))))
            except OSError:
                pass
    return str(max(stamps)) if stamps else ""


def site_settings(request):
    return {"site_settings": SiteSettings.load(), "asset_version": _asset_version()}
