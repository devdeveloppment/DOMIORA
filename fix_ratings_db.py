import sqlite3

def run():
    print("Tentative de correction de la base de données...")
    try:
        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(ratings_review)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'property_obj_id' not in columns:
            print("Colonne 'property_obj_id' manquante. Ajout en cours...")
            cursor.execute("ALTER TABLE ratings_review ADD COLUMN property_obj_id bigint REFERENCES properties_property(id);")
            conn.commit()
            print("Colonne 'property_obj_id' ajoutée avec succès !")
        else:
            print("La colonne 'property_obj_id' existe déjà.")
            
    except sqlite3.OperationalError as e:
        print(f"Erreur SQLite : {e}")
        print("Veuillez vous assurer que la table 'ratings_review' existe (vous avez peut-être besoin de faire 'python manage.py migrate ratings' d'abord).")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    run()
