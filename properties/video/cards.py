"""
Cartes de titre et de fin de la visite virtuelle.

Contenu autorisé : titre, type de bien, ville, quartier, « Découvrez ce bien sur DOMIORA ».
Jamais : adresse, prix, disponibilité, téléphone, email, nom ou coordonnées du propriétaire.
Le titre étant saisi librement par le propriétaire, il est filtré (prix, téléphones,
emails, liens) avant d'être incrusté.
"""
import re

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

BRAND = (90, 26, 36)          # primary-600
BRAND_DARK = (45, 12, 18)     # primary-900
ACCENT = (231, 165, 179)      # primary-300
WHITE = (255, 255, 255)

OUTRO_TEXT = "Découvrez ce bien sur DOMIORA"

_EMAIL_RE = re.compile(r"\S+@\S+")
_URL_RE = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?:\+?\d[\d .\-/]{6,}\d)")
_MONEY_RE = re.compile(
    r"\d[\d\s.,]*\s*(?:k|mille|millions?|milliards?|m)?\s*(?:f\s?cfa|fcfa|cfa|xof|francs?|€|eur|euros?|\$|usd|dollars?|f\b)",
    re.IGNORECASE,
)
_SHORT_MONEY_RE = re.compile(r"\d[\d\s.,]*\s*(?:k|mille|millions?|milliards?)\b", re.IGNORECASE)
_PRICE_WORDS_RE =re.compile(r"\b(prix|loyer|tarif|à partir de|a partir de|par mois|/mois|négociable|negociable)\b[^,–—\-|]*", re.IGNORECASE)
_CONTACT_WORDS_RE = re.compile(r"\b(tél|tel|téléphone|telephone|whatsapp|contact|appelez|appeler)\b\s*:?", re.IGNORECASE)


def sanitize_card_text(text, max_length=90):
    """Retire d'un texte libre tout ce qui ressemble à un prix, un contact ou un lien."""
    text = text or ""
    for pattern in (_EMAIL_RE, _URL_RE, _MONEY_RE, _SHORT_MONEY_RE, _PRICE_WORDS_RE, _PHONE_RE, _CONTACT_WORDS_RE):
        text = pattern.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(\s*[-–—|,:;/]\s*)+$", "", text)
    text = re.sub(r"^(\s*[-–—|,:;/]\s*)+", "", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text).strip()
    if len(text) > max_length:
        text = text[: max_length - 1].rsplit(" ", 1)[0] + "…"
    return text


def card_texts(prop):
    """Textes publics, non périssables, autorisés dans la vidéo."""
    from services.property_search import display_city

    location = " — ".join(part for part in [display_city(prop.city), (prop.neighborhood or "").strip()] if part)
    subtitle = " · ".join(part for part in [prop.get_property_type_display(), location] if part)
    return {
        "title": sanitize_card_text(prop.title) or prop.get_property_type_display(),
        "subtitle": sanitize_card_text(subtitle, max_length=80),
    }


def _font(size, bold=False):
    candidates = ["DejaVuSans-Bold.ttf", "arialbd.ttf"] if bold else ["DejaVuSans.ttf", "arial.ttf"]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _wrap(draw, text, font, max_width, max_lines):
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,;: ") + "…"
    return lines


def _background(size, cover_photo=None):
    width, height = size
    if cover_photo is not None:
        scale = max(width / cover_photo.width, height / cover_photo.height)
        bg = cover_photo.resize((max(width, int(cover_photo.width * scale)), max(height, int(cover_photo.height * scale))), Image.BILINEAR)
        left, top = (bg.width - width) // 2, (bg.height - height) // 2
        bg = bg.crop((left, top, left + width, top + height)).filter(ImageFilter.GaussianBlur(radius=max(8, width // 60)))
        bg = ImageEnhance.Brightness(bg).enhance(0.45)
        overlay = Image.new("RGB", size, BRAND_DARK)
        return Image.blend(bg, overlay, 0.35)
    # Dégradé de la couleur DOMIORA (aucune photo disponible)
    bg = Image.new("RGB", size, BRAND_DARK)
    draw = ImageDraw.Draw(bg)
    for y in range(height):
        t = y / max(height - 1, 1)
        color = tuple(int(BRAND[i] * (1 - t) + BRAND_DARK[i] * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    return bg


def _draw_centered(draw, lines, font, y, width, fill, spacing):
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text(((width - w) / 2, y), line, font=font, fill=fill)
        y += font.size + spacing
    return y


def render_title_card(texts, size, cover_photo=None):
    """Carte d'ouverture : « VISITE VIRTUELLE », titre, type · ville — quartier."""
    width, height = size
    img = _background(size, cover_photo)
    draw = ImageDraw.Draw(img)
    kicker_font = _font(max(12, height // 30), bold=True)
    title_font = _font(max(18, height // 13), bold=True)
    sub_font = _font(max(12, height // 26))

    title_lines = _wrap(draw, texts["title"], title_font, width * 0.82, 2)
    block = kicker_font.size + 24 + len(title_lines) * (title_font.size + 10) + 18 + sub_font.size
    y = (height - block) / 2
    y = _draw_centered(draw, ["VISITE VIRTUELLE"], kicker_font, y, width, ACCENT, 0) + 24
    y = _draw_centered(draw, title_lines, title_font, y, width, WHITE, 10) + 8
    line_w = width * 0.08
    draw.line([((width - line_w) / 2, y), ((width + line_w) / 2, y)], fill=ACCENT, width=max(2, height // 240))
    y += 18
    if texts.get("subtitle"):
        _draw_centered(draw, [texts["subtitle"]], sub_font, y, width, (235, 235, 235), 0)
    _draw_brand(draw, size)
    return img


def render_outro_card(texts, size, cover_photo=None):
    """Carte de fin : « Découvrez ce bien sur DOMIORA » + titre (aucune donnée dynamique)."""
    width, height = size
    img = _background(size, cover_photo)
    draw = ImageDraw.Draw(img)
    main_font = _font(max(18, height // 15), bold=True)
    title_font = _font(max(12, height // 28))
    lines = _wrap(draw, OUTRO_TEXT, main_font, width * 0.85, 2)
    title_lines = _wrap(draw, texts["title"], title_font, width * 0.8, 1)
    block = len(lines) * (main_font.size + 10) + 20 + title_font.size
    y = (height - block) / 2
    y = _draw_centered(draw, lines, main_font, y, width, WHITE, 10) + 20
    _draw_centered(draw, title_lines, title_font, y, width, ACCENT, 0)
    _draw_brand(draw, size)
    return img


def _draw_brand(draw, size):
    width, height = size
    font = _font(max(10, height // 34), bold=True)
    text = "DOMIORA"
    w = draw.textlength(text, font=font)
    draw.text(((width - w) / 2, height - font.size - height // 18), text, font=font, fill=(255, 255, 255))
