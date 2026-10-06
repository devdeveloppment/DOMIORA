"""
Storyboard et mouvements de caméra.

Chaque scène est rendue indépendamment, image par image (transformation affine
sous-pixel, donc sans les saccades du filtre zoompan), en ne gardant en mémoire
qu'UNE photo à la fois. La fenêtre de cadrage reste toujours à l'intérieur de la
photo : on ne fait que zoomer ou se déplacer dans ce qui existe.
"""
from dataclasses import dataclass, field
from typing import Optional

from PIL import Image, ImageEnhance, ImageFilter

from . import analysis

TRANSITION_DURATION = 0.6
CARD_DURATION = 3.0
_TRANSITIONS = ["fade", "smoothleft", "fade", "smoothright", "dissolve"]

# Amplitude des mouvements (1.10 = la fenêtre se resserre de 10 %)
_ZOOM = 1.10
_ESTABLISHING_ZOOM = 1.12
_PAN_ZOOM = 1.06
_PORTRAIT_ZOOM = 1.04
_CARD_ZOOM = 1.03


@dataclass
class Scene:
    kind: str                      # "title" | "photo" | "outro"
    duration: float
    motion: str
    source: Optional[str] = None   # chemin de la photo (scène "photo")
    transition: Optional[str] = None  # transition depuis la scène précédente
    image: Optional[Image.Image] = field(default=None, repr=False)  # carte déjà dessinée


def photo_duration(count):
    """Durée par photo adaptée au nombre de photos (vidéo finale ≈ 20 s à 70 s)."""
    if count <= 5:
        return 4.5
    if count <= 10:
        return 4.0
    if count <= 15:
        return 3.5
    return 3.0


def build_storyboard(photos, output_size, title_image=None, outro_image=None):
    """photos : liste de PhotoInfo, déjà dans l'ordre du propriétaire."""
    scenes = [Scene("title", CARD_DURATION, analysis.ZOOM_IN, image=title_image)]
    base = photo_duration(len(photos))
    for index, info in enumerate(photos):
        motion = analysis.choose_motion(info, index, output_size)
        duration = base + 1.0 if motion == analysis.ESTABLISHING else base
        transition = "fade" if index == 0 else _TRANSITIONS[index % len(_TRANSITIONS)]
        scenes.append(Scene("photo", duration, motion, source=info.path, transition=transition))
    scenes.append(Scene("outro", CARD_DURATION, analysis.ZOOM_IN, image=outro_image, transition="fadeblack"))
    return scenes


def expected_duration(scenes):
    return sum(s.duration for s in scenes) - TRANSITION_DURATION * (len(scenes) - 1)


# ---------------------------------------------------------------------------
# Rendu image par image
# ---------------------------------------------------------------------------
def _ease(t):
    return t * t * (3 - 2 * t)  # départ et arrivée en douceur


def _work_image(img, output_size, zoom):
    """
    Redimensionne une fois la photo : assez grande pour couvrir la sortie même
    zoomée (pas d'agrandissement inutile), sans conserver une image géante en mémoire.
    """
    out_w, out_h = output_size
    cover = max(out_w / img.width, out_h / img.height)
    scale = max(cover, min(1.0, cover * zoom))
    if abs(scale - 1.0) > 0.01:
        img = img.resize((max(out_w, round(img.width * scale)), max(out_h, round(img.height * scale))), Image.LANCZOS)
    return img


def _portrait_canvas(img, output_size):
    """Photo verticale présentée entière, sur un fond flouté et assombri de la même photo."""
    out_w, out_h = output_size
    canvas_size = (round(out_w * _PORTRAIT_ZOOM), round(out_h * _PORTRAIT_ZOOM))
    cover = max(canvas_size[0] / img.width, canvas_size[1] / img.height)
    bg = img.resize((round(img.width * cover) + 1, round(img.height * cover) + 1), Image.BILINEAR)
    left, top = (bg.width - canvas_size[0]) // 2, (bg.height - canvas_size[1]) // 2
    bg = bg.crop((left, top, left + canvas_size[0], top + canvas_size[1]))
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(radius=max(10, out_w // 40)))).enhance(0.5)
    fit = min(canvas_size[0] * 0.9 / img.width, canvas_size[1] * 0.94 / img.height)
    fg = img.resize((round(img.width * fit), round(img.height * fit)), Image.LANCZOS)
    bg.paste(fg, ((canvas_size[0] - fg.width) // 2, (canvas_size[1] - fg.height) // 2))
    return bg


def _windows(motion, work_size, output_size, frames):
    """Fenêtres de cadrage (x, y, largeur, hauteur) au format de sortie, à l'intérieur de l'image."""
    work_w, work_h = work_size
    ratio = output_size[0] / output_size[1]
    if work_w / work_h > ratio:
        full_h, full_w = work_h, work_h * ratio
    else:
        full_w, full_h = work_w, work_w / ratio

    def window(scale, fx, fy):
        w, h = full_w / scale, full_h / scale
        return (fx * (work_w - w), fy * (work_h - h), w, h)

    for i in range(frames):
        t = _ease(i / max(frames - 1, 1))
        if motion == analysis.ZOOM_IN:
            yield window(1 + (_ZOOM - 1) * t, 0.5, 0.5)
        elif motion == analysis.ZOOM_OUT:
            yield window(_ZOOM - (_ZOOM - 1) * t, 0.5, 0.5)
        elif motion == analysis.ESTABLISHING:
            yield window(_ESTABLISHING_ZOOM - (_ESTABLISHING_ZOOM - 1) * t, 0.5, 0.45)
        elif motion == analysis.PAN_RIGHT:
            yield window(_PAN_ZOOM, 0.1 + 0.8 * t, 0.5)
        elif motion == analysis.PAN_LEFT:
            yield window(_PAN_ZOOM, 0.9 - 0.8 * t, 0.5)
        elif motion == analysis.TILT_DOWN:
            yield window(_PAN_ZOOM, 0.5, 0.15 + 0.7 * t)
        elif motion == analysis.PORTRAIT:
            yield window(1 + (_PORTRAIT_ZOOM - 1) * t, 0.5, 0.5)
        else:  # cartes
            yield window(1 + (_CARD_ZOOM - 1) * t, 0.5, 0.5)


def iter_frames(scene, output_size, fps):
    """Génère les images RGB (bytes) de la scène, une à la fois."""
    if scene.kind == "photo":
        img = analysis.load_rgb(scene.source)
        if scene.motion == analysis.PORTRAIT:
            work = _portrait_canvas(img, output_size)
        else:
            zoom = {analysis.ESTABLISHING: _ESTABLISHING_ZOOM, analysis.ZOOM_IN: _ZOOM, analysis.ZOOM_OUT: _ZOOM}.get(scene.motion, _PAN_ZOOM)
            work = _work_image(img, output_size, zoom)
        del img
    else:
        work = scene.image.resize((round(output_size[0] * _CARD_ZOOM), round(output_size[1] * _CARD_ZOOM)), Image.LANCZOS)

    out_w, out_h = output_size
    frames = max(1, round(scene.duration * fps))
    for x, y, w, h in _windows(scene.motion, work.size, output_size, frames):
        frame = work.transform(output_size, Image.AFFINE, (w / out_w, 0, x, 0, h / out_h, y), resample=Image.BILINEAR)
        yield frame.tobytes()
