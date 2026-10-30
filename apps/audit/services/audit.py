"""Helper used throughout the codebase to log admin actions."""
import ipaddress
import logging

from django.conf import settings

from ..models import AuditLog

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Katalogi ya ujumbe wa lugha mbili (sw, en) kwa kila action.
# Mtumie hivi:  log_action(request=request, action="listing.approved",
#                          target=listing.title, params={"name": listing.title})
# Hii inahakikisha details_sw na details_en ZOTE mbili zinajazwa kila wakati,
# bila kila caller kuandika tafsiri mwenyewe.
# Placeholders: {name}, {reason}, {count}, {role}, {user}, {code}, {old}, {new}, {fields}, {ids}, {items}, {days}, {name}.
# Kisichotolewa kinakuwa "—".
# ---------------------------------------------------------------------------
AUDIT_TEMPLATES = {
    # Listings (msingi)
    "listing.approved":  ('Tangazo "{name}" limeidhinishwa.', 'Listing "{name}" was approved.'),
    "listing.rejected":  ('Tangazo "{name}" limekataliwa. Sababu: {reason}', 'Listing "{name}" was rejected. Reason: {reason}'),
    "listing.deleted":   ('Tangazo "{name}" limefutwa.', 'Listing "{name}" was deleted.'),
    "listing.restored":  ('Tangazo "{name}" limerudishwa.', 'Listing "{name}" was restored.'),
    # Users (msingi)
    "user.suspended":    ('Mtumiaji "{name}" amesimamishwa. Sababu: {reason}', 'User "{name}" was suspended. Reason: {reason}'),
    "user.activated":    ('Mtumiaji "{name}" ameamilishwa.', 'User "{name}" was activated.'),
    "user.verified":     ('Mtumiaji "{name}" amethibitishwa.', 'User "{name}" was verified.'),
    "user.deleted":      ('Mtumiaji "{name}" amefutwa.', 'User "{name}" was deleted.'),
    # Verifications
    "verification.approved": ('Uthibitisho wa "{name}" umekubaliwa.', 'Verification for "{name}" was approved.'),
    "verification.rejected": ('Uthibitisho wa "{name}" umekataliwa. Sababu: {reason}', 'Verification for "{name}" was rejected. Reason: {reason}'),
    # Deals / disputes / refunds
    "dispute.resolved":  ('Mgogoro "{name}" umetatuliwa.', 'Dispute "{name}" was resolved.'),
    "deal.cancelled":    ('Muamala "{name}" umefutwa.', 'Deal "{name}" was cancelled.'),
    "refund.issued":     ('Marejesho yametolewa kwa "{name}".', 'Refund issued for "{name}".'),
    # Fees (msingi)
    "fee.updated":       ('Ada "{name}" imebadilishwa.', 'Fee "{name}" was updated.'),
    # Categories
    "category.created":  ('Kategoria "{name}" imeundwa.', 'Category "{name}" was created.'),
    "category.updated":  ('Kategoria "{name}" imebadilishwa.', 'Category "{name}" was updated.'),
    "category.deleted":  ('Kategoria "{name}" imefutwa.', 'Category "{name}" was deleted.'),
    # Announcements
    "announcement.created": ('Tangazo la mfumo "{name}" limeundwa.', 'Announcement "{name}" was created.'),
    "announcement.sent":    ('Tangazo la mfumo "{name}" limetumwa.', 'Announcement "{name}" was sent.'),
    "announcement.deleted": ('Tangazo la mfumo "{name}" limefutwa.', 'Announcement "{name}" was deleted.'),
    # Content banners
    "content.banner.created": ('Banner "{name}" imeundwa.', 'Banner "{name}" was created.'),
    "content.banner.updated": ('Banner "{name}" imebadilishwa.', 'Banner "{name}" was updated.'),
    "content.banner.deleted": ('Banner "{name}" imefutwa.', 'Banner "{name}" was deleted.'),
    # Bundles
    "bundle.created":    ('Kifurushi "{name}" kimeundwa.', 'Bundle "{name}" was created.'),
    "bundle.updated":    ('Kifurushi "{name}" kimebadilishwa.', 'Bundle "{name}" was updated.'),
    "bundle.deleted":    ('Kifurushi "{name}" kimefutwa.', 'Bundle "{name}" was deleted.'),
    # RBAC
    "rbac.role.created": ('Role "{name}" imeundwa.', 'Role "{name}" was created.'),
    "rbac.role.updated": ('Role "{name}" imebadilishwa.', 'Role "{name}" was updated.'),
    "rbac.role.deleted": ('Role "{name}" imefutwa.', 'Role "{name}" was deleted.'),
    "rbac.staff.assigned": ('Role "{role}" imepewa "{user}".', 'Role "{role}" was assigned to "{user}".'),
    "rbac.staff.removed":  ('Role "{role}" imeondolewa kwa "{user}".', 'Role "{role}" was removed from "{user}".'),
    # Trash (msingi)
    "trash.restored":      ('"{name}" imerudishwa kutoka tupio.', '"{name}" was restored from trash.'),
    "trash.hard_deleted":  ('"{name}" imefutwa kabisa.', '"{name}" was permanently deleted.'),
    # System
    "webhook.created":   ('Webhook "{name}" imeundwa.', 'Webhook "{name}" was created.'),
    "webhook.deleted":   ('Webhook "{name}" imefutwa.', 'Webhook "{name}" was deleted.'),
    "system.policy.updated": ('Sera ya mfumo "{name}" imebadilishwa.', 'System policy "{name}" was updated.'),
    # Audit
    "audit.deleted":     ('Log imefutwa: {name}', 'Log deleted: {name}'),
    "audit.cleared":     ('Logs {count} zimefutwa.', 'Cleared {count} audit logs.'),

    # ============================================================
    # PATCH 1 TEMPLATES
    # ============================================================
    # Users (mpya)
    "user.updated": ('Mtumiaji "{name}" amebadilishwa. Sehemu: {fields}', 'User "{name}" was updated. Fields: {fields}'),
    "user.permanent_deleted": ('Mtumiaji "{name}" amefutwa kabisa. Sababu: {reason}', 'User "{name}" was permanently deleted. Reason: {reason}'),
    # Listings moderation (mpya)
    "listing.disapproved":       ('Idhini ya tangazo "{name}" imeondolewa. Sababu: {reason}', 'Listing "{name}" was disapproved. Reason: {reason}'),
    "listing.marked_sold":       ('Tangazo "{name}" limewekwa kama LIMEUZWA.', 'Listing "{name}" was marked as SOLD.'),
    "listing.request_edit":      ('Marekebisho yameombwa kwa tangazo "{name}". Sababu: {reason}', 'Edit requested for listing "{name}". Reason: {reason}'),
    "listing.request_payment":   ('Malipo yameombwa kwa tangazo "{name}".', 'Payment requested for listing "{name}".'),
    "listing.finalize_approved": ('Idhini ya mwisho ya tangazo "{name}" imekamilika.', 'Listing "{name}" received final approval.'),
    "listing.bulk_approved":     ('Matangazo {count} yameidhinishwa kwa pamoja. IDs: {ids}', 'Bulk approved {count} listings. IDs: {ids}'),
    "listing.bulk_rejected":     ('Matangazo {count} yamekataliwa kwa pamoja. IDs: {ids}', 'Bulk rejected {count} listings. IDs: {ids}'),
    "listing.bulk_deleted":      ('Matangazo {count} yamefutwa kwa pamoja. IDs: {ids}', 'Bulk deleted {count} listings. IDs: {ids}'),
    # Tickets (mpya)
    "ticket.created":              ('Tiketi {code} imeundwa: {name}', 'Ticket {code} was created: {name}'),
    "ticket.message_added":        ('Ujumbe umeongezwa kwenye tiketi {code} na {user} (viambatisho: {count}).', 'Message added to ticket {code} by {user} (attachments: {count}).'),
    "ticket.attachments_uploaded": ('Viambatisho {count} vimepakiwa kwenye tiketi {code}.', '{count} attachments were uploaded to ticket {code}.'),
    "ticket.status_changed":       ('Hali ya tiketi {code} imebadilishwa: {old} → {new}.', 'Status of ticket {code} changed: {old} → {new}.'),
    "ticket.priority_changed":     ('Kipaumbele cha tiketi {code} kimebadilishwa: {old} → {new}.', 'Priority of ticket {code} changed: {old} → {new}.'),
    "ticket.assigned":             ('Tiketi {code} imekabidhiwa: {old} → {new}.', 'Ticket {code} was assigned: {old} → {new}.'),
    "ticket.deleted":              ('Tiketi {code} imefutwa.', 'Ticket {code} was deleted.'),

    # ============================================================
    # PATCH 2 TEMPLATES
    # ============================================================
    # Fees (mpya)
    "fee.created": ('Ada "{name}" imeundwa.', 'Fee "{name}" was created.'),
    "fee.deleted": ('Ada "{name}" imefutwa.', 'Fee "{name}" was deleted.'),
    # Trash (mpya)
    "trash.refunds_created": ('Marejesho {count} yameundwa kwa "{name}": {items}', 'Created {count} refund(s) for "{name}": {items}'),
    "trash.cascade_deleted": ('Vitu {count} vinavyohusiana vimefutwa pamoja na "{name}": {items}', 'Cascade-deleted {count} related item(s) with "{name}": {items}'),
    # core.purge_soft_deleted (imesasishwa — sasa inatumika kwa kitu kimoja)
    "core.purge_soft_deleted": ('"{name}" imefutwa kabisa baada ya siku {days} kwenye kikapu.', '"{name}" was permanently deleted after {days} days in trash.'),
}


class _Params(dict):
    def __missing__(self, key):
        return "\u2014"  # em dash


def render_details(action, params=None):
    """Rudisha (sw, en) kutoka kwenye katalogi, au None kama action haipo."""
    tpl = AUDIT_TEMPLATES.get(action)
    if not tpl:
        return None
    p = _Params({k: ("\u2014" if v in (None, "") else v) for k, v in (params or {}).items()})
    try:
        return tpl[0].format_map(p), tpl[1].format_map(p)
    except Exception:  # placeholder mbaya — usivunje request
        logger.exception("audit: failed to render template for %s", action)
        return None


def _client_ip(request):
    """Only trust XFF if REMOTE_ADDR is a trusted proxy."""
    trusted = getattr(settings, "TRUSTED_PROXY_CIDRS", [])
    meta = getattr(request, "META", {}) if request else {}
    remote = meta.get("REMOTE_ADDR", "")

    if trusted and remote:
        try:
            remote_ip = ipaddress.ip_address(remote)
            is_trusted = any(
                remote_ip in ipaddress.ip_network(cidr, strict=False)
                for cidr in trusted
            )
        except ValueError:
            is_trusted = False

        if is_trusted:
            xff = meta.get("HTTP_X_FORWARDED_FOR", "")
            if xff:
                return xff.split(",")[0].strip()

    return remote or None


def _split_details(details, details_sw, details_en):
    """
    Inarudisha (legacy, sw, en).
    Inashughulikia kama `details` ni dict au string ya kawaida.
    """
    if isinstance(details, dict):
        details_sw = details_sw or details.get("sw") or ""
        details_en = details_en or details.get("en") or ""
        details = ""
    details = details or ""
    details_sw = details_sw or ""
    details_en = details_en or ""
    legacy = details or details_sw or details_en
    return legacy, details_sw, details_en


def log_action(*, request, action, target="", target_id=None,
               details="", details_sw="", details_en="", admin=None,
               params=None):
    """
    Andika audit log. Njia tatu za kutoa maelezo (kutoka bora hadi ya zamani):
      1. params={...}                 -> ujumbe unatengenezwa kwa sw + en kutoka AUDIT_TEMPLATES
      2. details={"sw": "..", "en": ".."} au details_sw=/details_en=
      3. details="..."                -> lugha MOJA tu (inatoa onyo kwenye logs; epuka)
    """
    user = admin or getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None

    meta = getattr(request, "META", {}) if request else {}

    has_explicit_bilingual = isinstance(details, dict) or bool(details_sw) or bool(details_en)
    if params is not None and not has_explicit_bilingual:
        rendered = render_details(action, params)
        if rendered:
            details_sw, details_en = rendered
            details = ""
        else:
            logger.warning(
                "audit: action=%r haipo kwenye AUDIT_TEMPLATES; maelezo yamepotea.",
                action,
            )

    legacy, d_sw, d_en = _split_details(details, details_sw, details_en)

    # Onyo: kuna maelezo lakini lugha moja pekee -> UI haiwezi kuyatafsiri
    if legacy and not (d_sw and d_en):
        logger.warning(
            "audit: action=%r ina maelezo ya lugha moja tu. "
            "Tumia params= au details={'sw':..,'en':..}.", action,
        )
    elif not legacy and not params and action in AUDIT_TEMPLATES:
        logger.info("audit: action=%r haina maelezo (params hazikutolewa).", action)

    return AuditLog.objects.create(
        action=action,
        admin_user=user,
        admin_name=getattr(user, "name", "") or "",
        target=target or "",
        target_id=target_id,
        details=legacy,
        details_sw=d_sw,
        details_en=d_en,
        ip_address=_client_ip(request),
        user_agent=(meta.get("HTTP_USER_AGENT", "") or "")[:255],
        request_path=(getattr(request, "path", "") or "")[:500],
        request_method=(getattr(request, "method", "") or "")[:10],
    )