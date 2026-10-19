"""Accès contrôlé aux fichiers sensibles (jamais d'URL publique)."""
import mimetypes

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from .private_storage import open_private


def _is_admin(user):
    return user.is_authenticated and (user.is_superuser or getattr(user, "role", "") == "admin")


def private_file_response(fieldfile):
    if not fieldfile:
        raise Http404
    try:
        handle = open_private(fieldfile)
    except FileNotFoundError:
        raise Http404
    content_type = mimetypes.guess_type(fieldfile.name)[0] or "application/octet-stream"
    response = FileResponse(handle, content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Disposition"] = "inline"
    return response


def identity_document(request, pk, side):
    from accounts.models import IdentityVerificationRequest

    if not _is_admin(request.user) or side not in ("recto", "verso"):
        raise Http404
    verification = get_object_or_404(IdentityVerificationRequest, pk=pk)
    return private_file_response(verification.id_document_front if side == "recto" else verification.id_document_back)


def user_identity_document(request, pk):
    from accounts.models import User

    if not _is_admin(request.user):
        raise Http404
    return private_file_response(get_object_or_404(User, pk=pk).id_document)


def property_document(request, pk):
    from properties.models import PropertyDocument

    doc = get_object_or_404(PropertyDocument.objects.select_related("property"), pk=pk)
    if not (_is_admin(request.user) or (request.user.is_authenticated and doc.property.owner_id == request.user.pk)):
        raise Http404
    return private_file_response(doc.file)
