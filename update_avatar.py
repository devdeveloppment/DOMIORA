import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User
import shutil
from django.core.files import File

admin_users = User.objects.filter(role='admin')
if admin_users.exists():
    admin = admin_users.first()
    # Find the latest picture in media/settings
    settings_dir = 'media/settings'
    if os.path.exists(settings_dir):
        files = [os.path.join(settings_dir, f) for f in os.listdir(settings_dir) if f.endswith('.png')]
        if files:
            latest_file = max(files, key=os.path.getctime)
            
            # Copy it to avatars
            avatars_dir = 'media/avatars'
            os.makedirs(avatars_dir, exist_ok=True)
            new_path = os.path.join(avatars_dir, 'admin_avatar.png')
            shutil.copy(latest_file, new_path)
            
            with open(new_path, 'rb') as f:
                admin.avatar.save('admin_avatar.png', File(f), save=True)
            print(f"Updated avatar for {admin.username} with {latest_file}")
        else:
            print("No png files found in media/settings")
    else:
        print("media/settings not found")
else:
    print("No admin users found")
