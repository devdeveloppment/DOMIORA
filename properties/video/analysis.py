"""
Analyse géométrique déterministe des photos (aucune IA).

On ne lit que l'en-tête de l'image (taille, orientation EXIF) : les pixels ne
sont décodés qu'au moment du rendu de la scène correspondante.
"""
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

# Mouvements disponibles (tous restent dans les limites de la photo : rien n'est inventé)
ZOOM_IN = "zoom_in"
ZOOM_OUT = "zoom_out"
PAN_RIGHT = "pan_right"
PAN_LEFT = "pan_left"
TILT_DOWN = "tilt_down"
PORTRAIT = "portrait"
ESTABLISHING = "establishing"

_LANDSCAPE_CYCLE = [ZOOM_IN, PAN_RIGHT, ZOOM_OUT, PAN_LEFT]


@dataclass
class PhotoInfo:
    path: str
    width: int
    height: int

    @property
    def aspect(self):
        return self.width / self.height if self.height else 1.0

    @property
    def orientation(self):
        if self.aspect < 0.9:
            return "portrait"
        if self.aspect > 1.9:
            return "panoramic"
        if self.aspect < 1.45:
            return "square"
        return "landscape"


class UnreadablePhoto(Exception):
    pass


def read_photo_info(path):
    """Dimensions réelles (après rotation EXIF) sans décoder toute l'image."""
    try:
        with Image.open(path) as img:
            width, height = img.size
            orientation = img.getexif().get(0x0112, 1)
            if orientation in (5, 6, 7, 8):  # rotation de 90° : dimensions inversées
                width, height = height, width
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise UnreadablePhoto(str(error)) from error
    if width < 32 or height < 32:
        raise UnreadablePhoto("image trop petite")
    return PhotoInfo(path=path, width=width, height=height)


def choose_motion(info, index, output_size):
    """
    Choisit un mouvement adapté au cadrage :
    - première photo (photo de couverture du propriétaire) : plan d'ouverture large et lent ;
    - photo verticale : présentée entière sur fond flouté de la même photo, zoom très léger ;
    - panorama : travelling horizontal ;
    - photo presque carrée : panoramique vertical doux ;
    - paysage : alternance zoom / travelling pour éviter la répétition.
    Une photo de faible résolution n'est jamais agrandie fortement.
    """
    out_w, _ = output_size
    if info.orientation == "portrait":
        return PORTRAIT
    if index == 0:
        return ESTABLISHING
    if info.orientation == "panoramic":
        return PAN_RIGHT if index % 2 else PAN_LEFT
    if info.orientation == "square":
        return TILT_DOWN
    motion = _LANDSCAPE_CYCLE[index % len(_LANDSCAPE_CYCLE)]
    if info.width < out_w * 0.75 and motion in (ZOOM_IN, ZOOM_OUT):
        return PAN_RIGHT if index % 2 else PAN_LEFT  # éviter un zoom qui flouterait une petite photo
    return motion


def load_rgb(path):
    """Décode une photo (rotation EXIF appliquée) au moment du rendu de sa scène."""
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        return img.convert("RGB")
