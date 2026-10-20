from django.middleware.gzip import GZipMiddleware


class SelectiveGZipMiddleware(GZipMiddleware):
    """GZip sauf pour les médias : images déjà compressées, et le client HTTP
    de l'app mobile échoue à décoder les FileResponse gzippées."""

    def process_response(self, request, response):
        if request.path.startswith("/media/"):
            return response
        return super().process_response(request, response)
