# Scripts hérités (diagnostic / réparation ponctuelle)

Scripts déplacés depuis la racine le 2026-10-19. Ils ne sont appelés ni par `build.sh`,
ni par `start.sh`, ni par Render. Ils ne sont pas découverts par `manage.py test`.

Certains modifient la base (`fix_*`, `cleanup_*`, `assign_*`, `update_*`, `create_admin.py`).
Ne les lancer qu'en connaissance de cause, sur une copie de la base :

    PYTHONPATH=. python scripts/legacy/<script>.py

`create_admin.py` contient un mot de passe par défaut : ne jamais l'utiliser en production.
Les `test_*cinetpay*` concernent un fournisseur abandonné (FedaPay uniquement).
