import urllib.request
import urllib.error

urls = [
    'http://127.0.0.1:8000/dashboard/client/',
    'http://127.0.0.1:8000/dashboard/proprietaire/',
    'http://127.0.0.1:8000/dashboard/proprietaire/profil/'
]

for url in urls:
    try:
        # Since these pages require auth, they might redirect to login. That's fine, a redirect is a 200 or 302.
        req = urllib.request.urlopen(url)
        print(f"{url}: {req.status}")
    except urllib.error.HTTPError as e:
        print(f"{url}: {e.code}")
    except Exception as e:
        print(f"{url}: {e}")
