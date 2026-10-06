from django.core.files.storage import default_storage
from PIL import Image
import io
from django.core.files.base import ContentFile


class WebPStorage:
    """Storage backend that converts images to WebP format"""
    
    def __init__(self, storage=default_storage):
        self.storage = storage
    
    def __getattr__(self, name):
        return getattr(self.storage, name)
    
    def _save(self, name, content):
        # Read the image
        img = Image.open(content)
        
        # Convert to RGB if necessary (WebP doesn't support RGBA with some configurations)
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        # Save as WebP with good quality
        webp_io = io.BytesIO()
        img.save(webp_io, format='WebP', quality=85, method=6)
        webp_io.seek(0)
        
        # Change extension to .webp
        webp_name = name.rsplit('.', 1)[0] + '.webp'
        
        # Save using the original storage
        return self.storage._save(webp_name, ContentFile(webp_io.read(), name=webp_name))


webp_storage = WebPStorage()