# Pharmacie du foyer

Application web pour suivre le stock de médicaments de la maison et le comparer aux ordonnances en cours, afin de savoir ce qu'il faut racheter.

- **À acheter** : ce qui manque pour couvrir les traitements en cours, les médicaments périmés et ceux qui vont bientôt périmer.
- **Stock** : les boîtes, rangées par lot et par date de péremption. Le code DataMatrix de la boîte peut être scanné (Chrome sur Android).
- **Ordonnances** : les traitements de chaque personne, avec une photo de l'ordonnance si on le souhaite.
- **Foyer** : les personnes de la maison, la sauvegarde et la restauration des données, et l'installation sur le téléphone.

Toutes les données restent sur l'appareil, dans le navigateur. Rien n'est envoyé sur internet. L'application s'installe sur l'écran d'accueil et fonctionne sans connexion.

Ce prototype suit un stock. Il ne remplace pas l'avis d'un médecin ou d'un pharmacien.

## Mettre à jour

Après avoir modifié un fichier, changez `VERSION` dans `sw.js` : les téléphones téléchargeront alors la nouvelle version.
