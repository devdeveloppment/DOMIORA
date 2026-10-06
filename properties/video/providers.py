"""
Fournisseurs de rendu vidéo.

VideoProvider définit le contrat ; FFmpegLocalProvider est la seule implémentation
active (aucun service payant, aucune IA générative : rendu fidèle aux photos).

Un futur ExternalVideoProvider (image-to-video) pourra implémenter render_scene()
en appelant une API externe — clé via variable d'environnement, jamais dans le code —
sans modifier le pipeline, le stockage ni les vues. Il devra rester fidèle aux photos.
"""
import os
from abc import ABC, abstractmethod

from . import ffmpeg, scenes


class VideoProvider(ABC):
    name = "abstract"

    @abstractmethod
    def render_scene(self, scene, index, workdir, output_size, fps):
        """Rend une scène ; retourne (chemin_du_clip, durée_réelle_en_secondes)."""

    @abstractmethod
    def assemble(self, clips, transitions, workdir, fps, out_path):
        """Assemble les clips avec leurs transitions ; retourne la durée totale."""


class FFmpegLocalProvider(VideoProvider):
    name = "ffmpeg_local"

    def render_scene(self, scene, index, workdir, output_size, fps):
        path = os.path.join(workdir, f"scene_{index:02d}.mp4")
        frames = max(1, round(scene.duration * fps))
        ffmpeg.encode_frames(scenes.iter_frames(scene, output_size, fps), output_size, fps, path)
        return path, frames / fps

    def assemble(self, clips, transitions, workdir, fps, out_path):
        return ffmpeg.assemble(clips, transitions, scenes.TRANSITION_DURATION, fps, workdir, out_path)


def get_provider():
    return FFmpegLocalProvider()
