"""
Accès à FFmpeg : encodage des scènes, assemblage avec transitions, vérification du rendu.

Les messages bruts de FFmpeg restent dans les logs ; les exceptions levées ici
portent un message technique qui n'est jamais affiché tel quel à l'utilisateur.
"""
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile

from django.conf import settings

logger = logging.getLogger(__name__)

ASSEMBLY_CHUNK = 6          # nombre maximal de clips décodés simultanément pendant l'assemblage
INTERMEDIATE_CRF = "18"     # clips intermédiaires de haute qualité
FINAL_CRF = "23"


class FFmpegUnavailable(Exception):
    pass


class FFmpegError(Exception):
    pass


class VideoValidationError(Exception):
    pass


def ffmpeg_binary():
    """FFMPEG_BINARY > ffmpeg du PATH > binaire fourni par imageio-ffmpeg."""
    configured = getattr(settings, "FFMPEG_BINARY", "")
    if configured:
        return configured
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as error:  # paquet absent ou binaire introuvable
        raise FFmpegUnavailable("Aucun binaire FFmpeg disponible") from error


def ffprobe_binary():
    found = shutil.which("ffprobe")
    if found:
        return found
    try:
        sibling = os.path.join(os.path.dirname(ffmpeg_binary()), "ffprobe" + (".exe" if os.name == "nt" else ""))
    except FFmpegUnavailable:
        return None
    return sibling if os.path.exists(sibling) else None


def _run(args, timeout=600):
    """Exécute FFmpeg ; en cas d'échec, journalise la fin de stderr et lève FFmpegError."""
    with tempfile.TemporaryFile() as err:
        try:
            completed = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=err, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise FFmpegError("FFmpeg timeout") from error
        err.seek(0)
        stderr = err.read().decode("utf-8", errors="replace")
    if completed.returncode != 0:
        logger.error("FFmpeg failed (code %s): %s", completed.returncode, stderr[-2000:])
        raise FFmpegError(f"FFmpeg exited with code {completed.returncode}")
    return stderr


def encode_frames(frames, output_size, fps, out_path):
    """Encode un flux d'images RGB brutes (une à la fois) en clip H.264."""
    width, height = output_size
    args = [
        ffmpeg_binary(), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", INTERMEDIATE_CRF, "-pix_fmt", "yuv420p",
        out_path,
    ]
    with tempfile.TemporaryFile() as err:
        process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=err)
        try:
            for frame in frames:
                process.stdin.write(frame)
        except (BrokenPipeError, OSError):
            pass  # FFmpeg s'est arrêté : le code retour ci-dessous le signale
        finally:
            try:
                process.stdin.close()
            except OSError:
                pass
            returncode = process.wait(timeout=600)
        if returncode != 0:
            err.seek(0)
            logger.error("FFmpeg scene encoding failed (code %s): %s", returncode, err.read().decode("utf-8", "replace")[-2000:])
            raise FFmpegError(f"FFmpeg exited with code {returncode}")
    return out_path


def _xfade(clips, transitions, transition_duration, fps, out_path, final):
    """Assemble ≤ ASSEMBLY_CHUNK clips avec des transitions xfade. clips = [(chemin, durée)]."""
    args = [ffmpeg_binary(), "-y", "-loglevel", "error"]
    for path, _ in clips:
        args += ["-i", path]
    if len(clips) == 1:
        filter_graph, last = "[0:v]settb=AVTB,fps={fps},format=yuv420p[vout]".format(fps=fps), "[vout]"
        total = clips[0][1]
    else:
        parts = [f"[{i}:v]settb=AVTB,fps={fps},format=yuv420p[s{i}]" for i in range(len(clips))]
        last, total = "[s0]", clips[0][1]
        for i in range(1, len(clips)):
            offset = total - transition_duration
            out = f"[x{i}]"
            parts.append(f"{last}[s{i}]xfade=transition={transitions[i - 1]}:duration={transition_duration}:offset={offset:.3f}{out}")
            last, total = out, total + clips[i][1] - transition_duration
        filter_graph = ";".join(parts)
    args += ["-filter_complex", filter_graph, "-map", last, "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if final:
        args += ["-preset", "medium", "-crf", FINAL_CRF, "-movflags", "+faststart"]
    else:
        args += ["-preset", "veryfast", "-crf", INTERMEDIATE_CRF]
    args.append(out_path)
    _run(args)
    return total


def assemble(clips, transitions, transition_duration, fps, workdir, out_path):
    """
    Assemble les clips par blocs (mémoire bornée) : chaque bloc de ≤ ASSEMBLY_CHUNK clips
    est assemblé, puis les blocs sont assemblés entre eux avec la transition de jonction.
    transitions[i] = transition entre clips[i] et clips[i+1].
    """
    level = 0
    while len(clips) > ASSEMBLY_CHUNK:
        grouped, joins = [], []
        for start in range(0, len(clips), ASSEMBLY_CHUNK):
            group = clips[start:start + ASSEMBLY_CHUNK]
            inner = transitions[start:start + len(group) - 1]
            path = os.path.join(workdir, f"chunk_{level}_{start}.mp4")
            duration = _xfade(group, inner, transition_duration, fps, path, final=False)
            grouped.append((path, duration))
            if start + len(group) < len(clips):
                joins.append(transitions[start + len(group) - 1])
        clips, transitions, level = grouped, joins, level + 1
    return _xfade(clips, transitions, transition_duration, fps, out_path, final=True)


def add_music(video_path, music_path, duration, out_path):
    """Musique de fond facultative (VIRTUAL_TOUR_MUSIC_PATH), avec fondu de sortie."""
    fade_start = max(0.0, duration - 2.0)
    _run([
        ffmpeg_binary(), "-y", "-loglevel", "error", "-i", video_path, "-stream_loop", "-1", "-i", music_path,
        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        "-af", f"afade=t=out:st={fade_start:.2f}:d=2", "-shortest", "-movflags", "+faststart", out_path,
    ])
    return out_path


# ---------------------------------------------------------------------------
# Vérification du rendu
# ---------------------------------------------------------------------------
def probe(path):
    """Retourne {"duration", "codec", "width", "height", "format"} via ffprobe, sinon via ffmpeg -i."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise VideoValidationError("Fichier vidéo absent ou vide")
    ffprobe = ffprobe_binary()
    if ffprobe:
        completed = subprocess.run(
            [ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
            capture_output=True, text=True, timeout=60,
        )
        if completed.returncode != 0:
            raise VideoValidationError("ffprobe ne peut pas lire la vidéo")
        data = json.loads(completed.stdout or "{}")
        video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
        if not video:
            raise VideoValidationError("Aucun flux vidéo")
        return {
            "duration": float(data.get("format", {}).get("duration") or video.get("duration") or 0),
            "codec": video.get("codec_name"),
            "width": int(video.get("width") or 0),
            "height": int(video.get("height") or 0),
            "format": data.get("format", {}).get("format_name", ""),
        }
    # Repli (imageio-ffmpeg ne fournit pas ffprobe) : analyse de « ffmpeg -i »
    completed = subprocess.run([ffmpeg_binary(), "-hide_banner", "-i", path], capture_output=True, text=True, timeout=60)
    info = completed.stderr
    duration = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", info)
    video = re.search(r"Stream #\S+.*?: Video: (\w+).*?, (\d{2,5})x(\d{2,5})", info)
    container = re.search(r"Input #0, ([\w,]+), from", info)
    if not duration or not video:
        raise VideoValidationError("Aucun flux vidéo lisible")
    hours, minutes, seconds = duration.groups()
    return {
        "duration": int(hours) * 3600 + int(minutes) * 60 + float(seconds),
        "codec": video.group(1),
        "width": int(video.group(2)),
        "height": int(video.group(3)),
        "format": container.group(1) if container else "",
    }


def validate(path, expected_duration, output_size, tolerance=1.5):
    """Vérifie existence, conteneur MP4, flux H.264, résolution, durée, puis décode entièrement la vidéo."""
    info = probe(path)
    if "mp4" not in info["format"] and "mov" not in info["format"]:
        raise VideoValidationError(f"Format inattendu : {info['format']}")
    if info["codec"] != "h264":
        raise VideoValidationError(f"Codec inattendu : {info['codec']}")
    if (info["width"], info["height"]) != tuple(output_size):
        raise VideoValidationError(f"Résolution inattendue : {info['width']}x{info['height']}")
    if info["duration"] < 1 or abs(info["duration"] - expected_duration) > tolerance:
        raise VideoValidationError(f"Durée inattendue : {info['duration']:.2f}s (attendu {expected_duration:.2f}s)")
    # Décodage complet : détecte un fichier tronqué ou corrompu.
    decode_errors = _run([ffmpeg_binary(), "-v", "error", "-i", path, "-f", "null", "-"], timeout=300)
    if decode_errors.strip():
        logger.error("Generated video has decoding errors: %s", decode_errors[-1000:])
        raise VideoValidationError("Erreurs de décodage")
    return info
