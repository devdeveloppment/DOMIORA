import os
import tempfile
import subprocess
from django.core.files import File
from django.core.files.storage import default_storage
from celery import shared_task
from .models import Property

@shared_task
def generate_virtual_tour_task(property_id):
    try:
        prop = Property.objects.get(id=property_id)
    except Property.DoesNotExist:
        return "Propriété introuvable"

    images = prop.images.all()
    if images.count() < 2:
        prop.video_status = Property.VideoStatus.FAILED
        prop.save()
        return "Pas assez d'images pour une vidéo"

    prop.video_status = Property.VideoStatus.PROCESSING
    prop.save()

    with tempfile.TemporaryDirectory() as temp_dir:
        list_file_path = os.path.join(temp_dir, 'images_list.txt')
        output_video_path = os.path.join(temp_dir, f'tour_{prop.id}.mp4')
        
        import requests
        duration_per_image = 3  # 3 secondes par image pour une vidéo fluide

        with open(list_file_path, 'w') as f:
            downloaded_paths = []
            for i, img in enumerate(images):
                if img.image:
                    # Download image to temp_dir since Cloudinary/S3 paths aren't local
                    img_url = img.image.url
                    if img_url.startswith('/'):
                        from django.conf import settings
                        base_url = getattr(settings, 'BASE_URL', 'http://127.0.0.1:8000')
                        img_url = base_url + img_url
                        
                    local_img_path = os.path.join(temp_dir, f'img_{i}.jpg')
                    try:
                        response = requests.get(img_url, timeout=10)
                        if response.status_code == 200:
                            with open(local_img_path, 'wb') as img_f:
                                img_f.write(response.content)
                            downloaded_paths.append(local_img_path.replace('\\', '/'))
                            print(f"✅ Downloaded image {i}: {local_img_path}")
                    except Exception as e:
                        print(f"❌ Failed to download {img_url}: {e}")
                        pass
            
            print(f"Total downloaded images: {len(downloaded_paths)}")
            
            if not downloaded_paths:
                prop.video_status = Property.VideoStatus.FAILED
                prop.save()
                return "Impossible de télécharger les images pour la vidéo"

            for path in downloaded_paths:
                f.write(f"file '{path}'\n")
                f.write(f"duration {duration_per_image}\n")
            
            # Repetition pour la derniere image (requis par concat)
            f.write(f"file '{downloaded_paths[-1]}'\n")

        # Commande FFmpeg avec effet Ken Burns avancé pour simuler un mouvement de caméra
        # Crée un effet de "marche" dans la pièce avec zoom et panoramique
        ffmpeg_cmd = [
            'ffmpeg',
            '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file_path,
            '-vf', "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,zoompan=z='min(zoom+0.001,1.3)':d=125:x='iw/2-(iw/zoom/2)+sin(on/10)*50':y='ih/2-(ih/zoom/2)+cos(on/10)*30',fade=t=out:st=2.5:d=0.5,format=yuv420p",
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-r', '30',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            output_video_path
        ]

        try:
            print(f"Running FFmpeg command: {' '.join(ffmpeg_cmd)}")
            result = subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print(f"FFmpeg stdout: {result.stdout}")
            print(f"FFmpeg stderr: {result.stderr}")
            
            # Vérifier si le fichier vidéo existe et a une taille
            if not os.path.exists(output_video_path):
                raise Exception("Le fichier vidéo n'a pas été créé")
            
            video_size = os.path.getsize(output_video_path)
            print(f"Video size: {video_size} bytes")
            
            if video_size < 1000:
                raise Exception(f"La vidéo générée est trop petite ({video_size} bytes)")
            
            # Use local storage instead of Cloudinary for video files
            from django.core.files.storage import FileSystemStorage
            from django.conf import settings
            
            # Create custom local storage for videos
            video_storage = FileSystemStorage(
                location=settings.MEDIA_ROOT / "properties" / "generated_tours",
                base_url=settings.MEDIA_URL + "properties/generated_tours/"
            )
            
            with open(output_video_path, 'rb') as video_file:
                file_name = f"virtual_tour_prop_{prop.id}.mp4"
                saved_path = video_storage.save(file_name, File(video_file))
                # Store only the filename, not the full path
                prop.virtual_tour_video.name = f"properties/generated_tours/{file_name}"
                prop.video_status = Property.VideoStatus.DONE
                prop.save(update_fields=['virtual_tour_video', 'video_status'])
            
            return f"Vidéo générée avec succès : {prop.id} (taille: {video_size} bytes)"
            
        except subprocess.CalledProcessError as e:
            prop.video_status = Property.VideoStatus.FAILED
            prop.save()
            error_msg = e.stderr if e.stderr else str(e)
            print(f"FFmpeg Error: {error_msg}")
            return f"Erreur FFmpeg : {error_msg}"
        except Exception as e:
            prop.video_status = Property.VideoStatus.FAILED
            prop.save()
            print(f"Error: {str(e)}")
            return f"Erreur : {str(e)}"
