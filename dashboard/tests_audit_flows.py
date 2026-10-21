"""
Audit des parcours : inscription, connexion, publication et modification des biens,
vérification d'identité, demandes de mise en relation (doublons, validations, permissions).
"""
import io
import shutil
import tempfile
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import IdentityVerificationRequest, User
from payments.tests import SIMPLE_STATIC, make_property
from properties.models import Property, PropertyImage, PropertyUnlock
from rental_requests.models import PropertyRequest

TMP_MEDIA = tempfile.mkdtemp(prefix="domiora-audit-")
PASSWORD = "Domiora-Test-2026!"


def image_file(name="photo.jpg", size=(3000, 2000), fmt="JPEG"):
    buffer = io.BytesIO()
    Image.new("RGB", size, (120, 80, 40)).save(buffer, format=fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


def property_post(**overrides):
    data = {
        "title": "Appartement lumineux à Bè", "description": "Trois pièces, proche du marché.",
        "property_type": Property.PropertyType.APPARTEMENT, "transaction_type": Property.TransactionType.LOCATION,
        "price": "75000", "currency": "XOF", "country": "Togo", "city": "Lomé", "neighborhood": "Bè",
        "address": "", "latitude": "", "longitude": "", "bedrooms": "2", "bathrooms": "1",
        "surface_area": "80", "floors": "1", "year_built": "", "status": Property.Status.DISPONIBLE,
        "virtual_tour_url": "",
    }
    data.update(overrides)
    return data


@override_settings(STORAGES=SIMPLE_STATIC, MEDIA_ROOT=TMP_MEDIA, PRIVATE_MEDIA_ROOT=TMP_MEDIA + "/private",
                   PRIVATE_MEDIA_BACKEND="filesystem")
class AuditBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()
        patcher = mock.patch("dashboard.views_owner.request_virtual_tour", return_value=(True, "Visite virtuelle en préparation."))
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_owner(self, username="proprio", verified=True, **kw):
        return User.objects.create_user(
            username, email=kw.pop("email", f"{username}@exemple.tg"), password=PASSWORD, role=User.Role.OWNER,
            verification_status=User.VerificationStatus.APPROVED if verified else User.VerificationStatus.UNVERIFIED, **kw,
        )


class OwnerRegistrationTests(AuditBase):
    url = reverse("accounts:register_owner")

    def data(self, **kw):
        base = {"first_name": "Kossi", "last_name": "Mensah", "username": "kossi", "email": "kossi@exemple.tg",
                "phone": "", "whatsapp_number": "+228 90 00 00 00", "password1": PASSWORD, "password2": PASSWORD}
        base.update(kw)
        return base

    def test_success_logs_in_and_goes_to_identity_step(self):
        resp = self.client.post(self.url, self.data())
        self.assertRedirects(resp, reverse("dashboard:owner_verify_identity"))
        user = User.objects.get(username="kossi")
        self.assertEqual(user.role, User.Role.OWNER)
        self.assertEqual(user.verification_status, User.VerificationStatus.UNVERIFIED)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_duplicate_email_is_refused_case_insensitive(self):
        self.make_owner("ancien", email="kossi@exemple.tg")
        resp = self.client.post(self.url, self.data(email="KOSSI@Exemple.tg"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Un compte existe déjà avec cette adresse e-mail")
        self.assertFalse(User.objects.filter(username="kossi").exists())

    def test_double_submission_creates_a_single_account(self):
        self.client.post(self.url, self.data())
        self.client.logout()
        resp = self.client.post(self.url, self.data())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.filter(username="kossi").count(), 1)

    def test_invalid_phone_message(self):
        resp = self.client.post(self.url, self.data(whatsapp_number="abc"))
        self.assertContains(resp, "Numéro invalide")
        resp = self.client.post(self.url, self.data(phone="12"))
        self.assertContains(resp, "Numéro invalide")

    def test_email_is_stored_lowercase(self):
        self.client.post(self.url, self.data(email="Kossi@Exemple.TG"))
        self.assertEqual(User.objects.get(username="kossi").email, "kossi@exemple.tg")


class LoginTests(AuditBase):
    @override_settings(LOGIN_MAX_FAILURES=3)
    def test_failed_attempts_lock_the_account_temporarily(self):
        self.make_owner()
        url = reverse("accounts:login")
        for _ in range(3):
            self.client.post(url, {"username": "proprio", "password": "mauvais"})
        resp = self.client.post(url, {"username": "proprio", "password": PASSWORD})
        self.assertContains(resp, "Trop de tentatives")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_success_resets_the_counter(self):
        self.make_owner()
        url = reverse("accounts:login")
        self.client.post(url, {"username": "proprio", "password": "mauvais"})
        resp = self.client.post(url, {"username": "proprio", "password": PASSWORD})
        self.assertEqual(resp.status_code, 302)

    def test_admin_on_user_login_gets_clickable_link(self):
        User.objects.create_user("chef", password=PASSWORD, role=User.Role.ADMIN)
        resp = self.client.post(reverse("accounts:login"), {"username": "chef", "password": PASSWORD}, follow=True)
        self.assertContains(resp, f'<a href="{reverse("accounts:admin_login")}"', html=False)

    def test_client_login_does_not_reveal_whether_email_exists(self):
        User.objects.create_user("cli", email="cli@exemple.tg", password=PASSWORD, role=User.Role.CLIENT)
        url = reverse("accounts:client_login")
        unknown = self.client.post(url, {"email": "personne@exemple.tg", "password": "x"}, follow=True)
        wrong = self.client.post(url, {"email": "cli@exemple.tg", "password": "x"}, follow=True)
        self.assertContains(unknown, "E-mail ou mot de passe incorrect.")
        self.assertContains(wrong, "E-mail ou mot de passe incorrect.")

    def test_client_login_with_duplicate_emails_does_not_crash(self):
        User.objects.create_user("cli1", email="dup@exemple.tg", password="autre-Pass-1", role=User.Role.CLIENT)
        User.objects.create_user("cli2", email="DUP@exemple.tg", password=PASSWORD, role=User.Role.CLIENT)
        resp = self.client.post(reverse("accounts:client_login"), {"email": "dup@exemple.tg", "password": PASSWORD})
        self.assertRedirects(resp, reverse("dashboard:client_overview"), fetch_redirect_response=False)

    @override_settings(LOGIN_MAX_FAILURES=2)
    def test_api_token_is_throttled(self):
        self.make_owner()
        for _ in range(2):
            self.assertEqual(self.client.post("/api/auth/token/", {"username": "proprio", "password": "x"}).status_code, 400)
        self.assertEqual(self.client.post("/api/auth/token/", {"username": "proprio", "password": PASSWORD}).status_code, 429)

    def test_forms_are_protected_against_double_submission(self):
        body = self.client.get(reverse("accounts:register_owner")).content.decode()
        self.assertIn("js/form-guard.js", body)


class PropertyPublicationTests(AuditBase):
    def setUp(self):
        super().setUp()
        self.owner = self.make_owner()
        self.client.login(username="proprio", password=PASSWORD)
        self.url = reverse("dashboard:owner_property_create")

    def test_unverified_owner_cannot_publish(self):
        User.objects.filter(pk=self.owner.pk).update(verification_status=User.VerificationStatus.UNVERIFIED)
        resp = self.client.post(self.url, property_post())
        self.assertRedirects(resp, reverse("dashboard:owner_verify_identity"), fetch_redirect_response=False)
        self.assertFalse(Property.objects.exists())

    def test_form_is_in_french_with_local_defaults(self):
        body = self.client.get(self.url).content.decode()
        for label in ("Titre de l&#x27;annonce", "Type de bien", "Ville", "Chambres", "Disponibilité"):
            self.assertIn(label, body)
        self.assertIn('value="XOF"', body)
        self.assertNotIn("Mettre en avant", body)

    def test_invalid_form_keeps_input_and_shows_errors(self):
        resp = self.client.post(self.url, property_post(price="0", title="Villa avec jardin"))
        self.assertEqual(resp.status_code, 400)
        self.assertContains(resp, "Le bien n'a pas été enregistré", status_code=400)
        self.assertContains(resp, "Indiquez un prix supérieur à 0.", status_code=400)
        self.assertContains(resp, 'value="Villa avec jardin"', status_code=400)
        self.assertFalse(Property.objects.exists())

    def test_files_lost_notice_after_error(self):
        resp = self.client.post(self.url, {**property_post(city=""), "images": [image_file()]})
        self.assertContains(resp, "sélectionnez à nouveau vos photos", status_code=400)

    def test_created_pending_with_owner_and_photos(self):
        resp = self.client.post(self.url, {**property_post(is_featured="on"), "images": [image_file("a.jpg"), image_file("b.png", fmt="PNG")]})
        self.assertRedirects(resp, reverse("dashboard:owner_properties"), fetch_redirect_response=False)
        prop = Property.objects.get()
        self.assertEqual(prop.owner, self.owner)
        self.assertFalse(prop.is_published or prop.is_validated or prop.is_featured)
        self.assertEqual(prop.validation_status, Property.ValidationStatus.PENDING)
        images = list(prop.images.order_by("order"))
        self.assertEqual([i.order for i in images], [0, 1])
        self.assertTrue(images[0].is_primary and not images[1].is_primary)
        self.assertTrue(images[0].image.name.endswith(".webp"))
        with Image.open(images[0].image.path) as stored:
            self.assertLessEqual(max(stored.size), PropertyImage.MAX_PHOTO_SIDE)

    def test_long_phone_file_names_fit_in_database(self):
        long_name = "WhatsApp Image 2026-10-21 at 18.05.32 - copie de la photo du salon principal (2).jpeg"
        self.client.post(self.url, {**property_post(), "images": [image_file(long_name, (300, 200))]})
        stored = PropertyImage.objects.get().image.name
        self.assertTrue(stored.endswith(".webp"))
        self.assertLessEqual(len(stored), 60)
        self.assertEqual(PropertyImage._meta.get_field("image").max_length, 255)

    def test_fake_image_is_rejected(self):
        fake = SimpleUploadedFile("virus.jpg", b"MZ\x90\x00 pas une image", content_type="image/jpeg")
        resp = self.client.post(self.url, {**property_post(), "images": [fake]})
        self.assertContains(resp, "n&#x27;est pas une image lisible", status_code=400)
        self.assertFalse(Property.objects.exists())

    def test_too_many_images_rejected(self):
        with override_settings():
            with mock.patch("properties.forms.MAX_IMAGES_PER_UPLOAD", 2):
                resp = self.client.post(self.url, {**property_post(), "images": [image_file(f"{i}.jpg", (50, 50)) for i in range(3)]})
        self.assertContains(resp, "au maximum 2 photos", status_code=400)


class PropertyEditTests(AuditBase):
    def setUp(self):
        super().setUp()
        self.owner = self.make_owner()
        self.other = self.make_owner("voisin")
        self.prop = make_property(self.owner, title="Maison familiale")
        self.photo = PropertyImage.objects.create(property=self.prop, image=image_file("p.jpg", (200, 100)), order=0, is_primary=True)
        self.client.login(username="proprio", password=PASSWORD)
        self.url = reverse("dashboard:owner_property_edit", args=[self.prop.pk])

    def test_prefilled(self):
        body = self.client.get(self.url).content.decode()
        self.assertIn('value="Maison familiale"', body)
        self.assertIn('value="250000.00"', body)

    def test_update_persists_and_keeps_photos(self):
        resp = self.client.post(self.url, property_post(title="Maison familiale rénovée", price="300000"))
        self.assertRedirects(resp, reverse("dashboard:owner_properties"), fetch_redirect_response=False)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.title, "Maison familiale rénovée")
        self.assertEqual(int(self.prop.price), 300000)
        self.assertTrue(self.prop.is_validated)  # bien déjà validé : statut conservé (règle existante)
        self.assertEqual(list(self.prop.images.values_list("pk", flat=True)), [self.photo.pk])

    def test_new_photos_are_appended(self):
        self.client.post(self.url, {**property_post(), "images": [image_file("n.jpg", (100, 100))]})
        orders = list(self.prop.images.order_by("order").values_list("order", "is_primary"))
        self.assertEqual(orders, [(0, True), (1, False)])

    def test_cannot_edit_or_touch_photos_of_another_owner(self):
        self.client.logout()
        self.client.login(username="voisin", password=PASSWORD)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, property_post(title="Piraté")).status_code, 404)
        delete = reverse("dashboard:owner_property_image_delete", args=[self.prop.pk, self.photo.pk])
        self.assertEqual(self.client.post(delete).status_code, 404)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.title, "Maison familiale")
        self.assertTrue(PropertyImage.objects.filter(pk=self.photo.pk).exists())

    def test_state_changing_actions_require_post(self):
        delete = reverse("dashboard:owner_property_image_delete", args=[self.prop.pk, self.photo.pk])
        toggle = reverse("dashboard:owner_property_toggle_publish", args=[self.prop.pk])
        self.assertEqual(self.client.get(delete).status_code, 405)
        self.assertEqual(self.client.get(toggle).status_code, 405)
        self.assertTrue(PropertyImage.objects.filter(pk=self.photo.pk).exists())

    def test_unvalidated_property_cannot_be_put_online(self):
        pending = make_property(self.owner, title="En attente", is_published=False, is_validated=False)
        self.client.post(reverse("dashboard:owner_property_toggle_publish", args=[pending.pk]))
        pending.refresh_from_db()
        self.assertFalse(pending.is_published)

    def test_saving_an_existing_photo_does_not_reconvert_it(self):
        with mock.patch("PIL.Image.open") as opened:
            self.photo.order = 3
            self.photo.save()
        opened.assert_not_called()


class IdentityVerificationTests(AuditBase):
    def setUp(self):
        super().setUp()
        self.owner = self.make_owner(verified=False)
        self.client.login(username="proprio", password=PASSWORD)
        self.url = reverse("dashboard:owner_verify_identity")

    def post(self, front=None, back=None):
        return self.client.post(self.url, {
            "id_document_type": "cni", "id_document_number": "TG123",
            "id_document_front": front or image_file("recto.jpg", (400, 250)),
            "id_document_back": back or image_file("verso.jpg", (400, 250)),
        }, follow=True)

    def test_valid_submission(self):
        resp = self.post()
        self.assertContains(resp, "Vos documents ont été envoyés avec succès")
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.verification_status, User.VerificationStatus.PENDING_DOCUMENTS)
        self.assertEqual(IdentityVerificationRequest.objects.count(), 1)

    def test_fake_document_refused(self):
        resp = self.post(front=SimpleUploadedFile("recto.jpg", b"%PDF-1.4 faux", content_type="image/jpeg"))
        self.assertContains(resp, "n&#x27;est pas une image lisible")
        self.assertFalse(IdentityVerificationRequest.objects.exists())

    def test_no_duplicate_while_pending(self):
        self.post()
        resp = self.post()
        self.assertContains(resp, "déjà en cours d&#x27;analyse")
        self.assertEqual(IdentityVerificationRequest.objects.count(), 1)

    def test_approved_owner_status_is_never_downgraded(self):
        User.objects.filter(pk=self.owner.pk).update(verification_status=User.VerificationStatus.APPROVED)
        self.post()
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.verification_status, User.VerificationStatus.APPROVED)
        self.assertFalse(IdentityVerificationRequest.objects.exists())

    def test_logs_contain_no_document_number(self):
        with self.assertLogs("dashboard.views_owner", level="INFO") as logs:
            self.post()
        self.assertNotIn("TG123", "\n".join(logs.output))


class ContactRequestTests(AuditBase):
    def setUp(self):
        super().setUp()
        self.owner = self.make_owner()
        self.prop = make_property(self.owner)
        self.buyer = User.objects.create_user("acheteur", email="a@exemple.tg", password=PASSWORD, role=User.Role.CLIENT)
        PropertyUnlock.objects.create(user=self.buyer, property=self.prop)
        self.client.login(username="acheteur", password=PASSWORD)
        self.url = reverse("rental_requests:create")

    def test_duplicate_request_is_not_recreated(self):
        for _ in range(2):
            resp = self.client.post(self.url, {"property_id": self.prop.pk, "request_type": "visite"})
            self.assertEqual(resp.status_code, 302)
        self.assertEqual(PropertyRequest.objects.count(), 1)

    def test_invalid_values_do_not_crash(self):
        resp = self.client.post(self.url, {"property_id": self.prop.pk, "request_type": "visite", "move_in_date": "demain"})
        self.assertEqual(resp.status_code, 302)
        resp = self.client.post(self.url, {"property_id": self.prop.pk, "request_type": "pirate"})
        self.assertEqual(resp.status_code, 302)
        resp = self.client.post(self.url, {"property_id": "abc"})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(PropertyRequest.objects.exists())

    def test_json_errors_are_clean(self):
        resp = self.client.post(self.url, data='{"property_id": %d, "move_in_date": "2026-13-45"}' % self.prop.pk,
                                content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["message"], "Date d'emménagement invalide.")
