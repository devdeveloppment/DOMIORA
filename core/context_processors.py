from site_settings.models import SiteSettings


def site_settings(request):
    return {"site_settings": SiteSettings.load()}
