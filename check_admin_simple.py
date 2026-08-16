import sqlite3

# Connexion directe à la base de données
conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Chercher les utilisateurs avec le rôle admin
cursor.execute("SELECT username, email, is_superuser FROM accounts_user WHERE role = 'admin'")
admin_users = cursor.fetchall()

if admin_users:
    print(f"✅ {len(admin_users)} compte(s) administrateur(s) trouvé(s):")
    for username, email, is_superuser in admin_users:
        print(f"   - Nom d'utilisateur: {username}")
        print(f"     Email: {email}")
        print(f"     Est superuser: {is_superuser}")
else:
    print("❌ Aucun compte administrateur trouvé.")
    print("Vous pouvez en créer un via l'URL: http://127.0.0.1:8000/compte/admin-login/")

conn.close()
