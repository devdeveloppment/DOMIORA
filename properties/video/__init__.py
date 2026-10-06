"""
Génération des visites virtuelles DOMIORA.

    photos (ordre du propriétaire) → analyse géométrique → storyboard (scènes + mouvements)
    → rendu scène par scène (VideoProvider) → assemblage + transitions → titre / fin
    → vérification → stockage (Cloudinary en production) → Property.video_status = done

Point d'entrée pour les vues : properties.video.service.request_virtual_tour().
La visite virtuelle n'a aucun lien avec la mise en relation, le paiement FedaPay,
la demande de visite physique ou la vérification terrain.
"""
