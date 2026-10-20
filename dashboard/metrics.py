"""Indicateurs calculés à partir des opérations enregistrées en base.

Source unique des chiffres affichés dans les tableaux de bord : les cartes, graphiques et
tableaux d'une même période utilisent ces fonctions, ce qui garantit des totaux identiques.

Revenus de la plateforme = frais de mise en relation payés (PaymentAttempt approuvés)
+ paiements d'abonnement réussis (SubscriptionPayment). Chaque source est séparée en
« réel » (encaissé) et « test » (simulation, FedaPay sandbox, abonnements simulés) :
les montants de test ne sont jamais additionnés aux revenus réels.

Les Transaction (ventes/locations déclarées) ne sont PAS des revenus DOMIORA : leur
volume est présenté à part.
"""
from datetime import date, datetime, time, timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

PERIODS = {
    "30j": ("30 derniers jours", 30),
    "90j": ("90 derniers jours", 90),
    "12m": ("12 derniers mois", 365),
    "tout": ("Depuis le début", None),
}
DEFAULT_PERIOD = "12m"
MONTHS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def resolve_period(key):
    """Retourne (clé, libellé, date de début ou None) pour un paramètre ?periode=."""
    if key not in PERIODS:
        key = DEFAULT_PERIOD
    label, days = PERIODS[key]
    start = timezone.now() - timedelta(days=days) if days else None
    return key, label, start


def _since(qs, field, start):
    return qs.filter(**{f"{field}__gte": start}) if start else qs


def _sum_count(qs, amount_field="amount"):
    agg = qs.aggregate(total=Sum(amount_field), count=Count("id"))
    return {"total": int(agg["total"] or 0), "count": agg["count"] or 0}


def contact_fee_payments():
    from payments.models import PaymentAttempt

    return PaymentAttempt.objects.filter(status=PaymentAttempt.Status.APPROVED).annotate(
        paid_at=Coalesce("confirmed_at", "updated_at")
    )


def subscription_payments():
    from owner_subscriptions.models import SubscriptionPayment

    return SubscriptionPayment.objects.filter(status=SubscriptionPayment.Status.SUCCEEDED).annotate(
        paid_at=Coalesce("decided_at", "created_at")
    )


def finance_summary(start=None, owner=None):
    """Revenus réels et de test par source, sur la période (et éventuellement un propriétaire)."""
    from transactions.models import Transaction

    contacts = _since(contact_fee_payments(), "paid_at", start)
    subs = _since(subscription_payments(), "paid_at", start)
    deals = _since(Transaction.objects.all(), "transaction_date", start.date() if start else None)
    if owner is not None:
        contacts = contacts.filter(owner=owner)
        subs = subs.filter(owner=owner)
        deals = deals.filter(property__owner=owner)

    data = {
        "contact_real": _sum_count(contacts.filter(is_test=False)),
        "contact_test": _sum_count(contacts.filter(is_test=True)),
        "subs_real": _sum_count(subs.filter(is_simulated=False)),
        "subs_test": _sum_count(subs.filter(is_simulated=True)),
    }
    # Dons : affichés à part (contribution volontaire, pas un revenu de service).
    from core.models import Donation

    dons = _since(Donation.objects.filter(status=Donation.Status.APPROVED).annotate(
        paid_at=Coalesce("confirmed_at", "updated_at")), "paid_at", start)
    if owner is not None:
        dons = dons.none()
    data["donations_real"] = _sum_count(dons.filter(is_test=False))
    data["donations_test"] = _sum_count(dons.filter(is_test=True))
    data["real_total"] = data["contact_real"]["total"] + data["subs_real"]["total"]
    data["test_total"] = data["contact_test"]["total"] + data["subs_test"]["total"]
    deal_agg = deals.aggregate(volume=Sum("amount"), commission=Sum("commission_amount"), count=Count("id"))
    data["deals"] = {
        "volume": deal_agg["volume"] or 0,
        "commission": deal_agg["commission"] or 0,
        "count": deal_agg["count"] or 0,
    }
    return data


def _month_starts(months):
    today = timezone.localdate().replace(day=1)
    starts = []
    y, m = today.year, today.month
    for _ in range(months):
        starts.append(date(y, m, 1))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(starts))


def month_labels(months=6):
    return [f"{MONTHS_FR[s.month - 1]} {s.year}" for s in _month_starts(months)]


def monthly_revenue(months=6, owner=None):
    """Séries mensuelles (mois civils) : revenus réels et de test, toutes sources confondues."""
    starts = _month_starts(months)
    since = timezone.make_aware(datetime.combine(starts[0], time.min))
    buckets = {s: {"real": 0, "test": 0} for s in starts}
    sources = [
        (contact_fee_payments(), "is_test", True),
        (subscription_payments(), "is_simulated", True),
    ]
    for qs, flag, test_value in sources:
        qs = qs.filter(paid_at__gte=since)
        if owner is not None:
            qs = qs.filter(owner=owner)
        rows = qs.annotate(month=TruncMonth("paid_at")).values("month", flag).annotate(total=Sum("amount"))
        for row in rows:
            month = row["month"]
            key = (month.date() if isinstance(month, datetime) else month).replace(day=1)
            if key in buckets:
                buckets[key]["test" if row[flag] == test_value else "real"] += int(row["total"] or 0)
    return {
        "labels": month_labels(months),
        "real": [buckets[s]["real"] for s in starts],
        "test": [buckets[s]["test"] for s in starts],
    }


def monthly_counts(qs, date_field, months=6):
    """Nombre d'objets créés par mois civil (inscriptions, annonces, ...)."""
    starts = _month_starts(months)
    since = timezone.make_aware(datetime.combine(starts[0], time.min))
    rows = (
        qs.filter(**{f"{date_field}__gte": since})
        .annotate(month=TruncMonth(date_field)).values("month").annotate(n=Count("id"))
    )
    found = {}
    for row in rows:
        month = row["month"]
        found[(month.date() if isinstance(month, datetime) else month).replace(day=1)] = row["n"]
    return [found.get(s, 0) for s in starts]


def platform_counts(start=None):
    """Compteurs d'activité de la plateforme (utilisateurs, annonces, demandes, rendez-vous)."""
    from accounts.models import User
    from appointments.models import Appointment
    from owner_subscriptions.models import OwnerSubscription
    from properties.models import Property
    from rental_requests.models import PropertyRequest

    users = User.objects.all()
    props = Property.objects.all()
    counts = users.aggregate(
        clients=Count("id", filter=Q(role=User.Role.CLIENT)),
        owners=Count("id", filter=Q(role=User.Role.OWNER)),
        verified_owners=Count("id", filter=Q(role=User.Role.OWNER,
                                              verification_status=User.VerificationStatus.APPROVED)),
        new_users=Count("id", filter=Q(date_joined__gte=start) if start else Q()),
    )
    counts.update(props.aggregate(
        properties=Count("id"),
        published=Count("id", filter=Q(is_published=True, is_validated=True)),
        pending_validation=Count("id", filter=Q(is_validated=False)),
        for_rent=Count("id", filter=Q(transaction_type="location")),
        for_sale=Count("id", filter=Q(transaction_type="vente")),
        new_properties=Count("id", filter=Q(created_at__gte=start) if start else Q()),
        total_views=Sum("views_count"),
    ))
    counts["total_views"] = counts["total_views"] or 0
    counts["requests_pending"] = PropertyRequest.objects.filter(status="en_attente").count()
    counts["requests_period"] = _since(PropertyRequest.objects.all(), "created_at", start).count()
    counts["appointments_period"] = _since(Appointment.objects.all(), "created_at", start).count()
    counts["active_subscriptions"] = OwnerSubscription.objects.filter(status__in=["trial", "active"]).count()
    from moderation.models import ListingReport

    counts["reports_active"] = ListingReport.objects.filter(status__in=ListingReport.ACTIVE_STATUSES).count()
    counts["reports_period"] = _since(ListingReport.objects.all(), "created_at", start).count()
    return counts
