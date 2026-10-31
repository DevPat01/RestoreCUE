# Historique de la documentation

## Documentation V1.0 — 2026

- Rédaction du document de fonctionnement technique de RestoreCUE.
- Rédaction du document de tests et validations.
- Création des versions anglaises des deux documents.
- Documentation des échanges avec la console : `SHOWLIST`, `SETD`, `SAVECUE` et `CUELIST`.
- Présentation des résultats des essais réalisés sur une Soundcraft Ui24R réelle, sous Windows et Linux Mint.
- Documentation de la gestion des threads, de la connexion WebSocket et de sa fermeture.

# Historique des versions — RestoreCUE

Ce document résume les principales évolutions de RestoreCUE, de la version V7 à la version V10.

## V10 — Sélection et contrôles de restauration

- Recherche automatique des dossiers contenant des fichiers `.uicue` dans un répertoire et ses sous-répertoires.
- Sélection du dossier du Show par numéro, sans saisie manuelle de son chemin complet.
- Sélection de tous les Cues ou d'une partie des Cues à restaurer.
- Prise en charge de sélections par numéros et plages, par exemple `1-10` ou `11-20`.
- Vérification préalable de l'existence du Show sur la console avec `SHOWLIST`.
- Arrêt de la restauration si le Show recherché n'est pas présent ; aucun `SETD` ni `SAVECUE` n'est alors envoyé.
- Vérification finale des noms de Cues présents sur la console avec `CUELIST`.
- Affichage d'un bilan comprenant les Cues attendus, retrouvés et manquants.
- Gestion de l'arrêt des threads d'observation et `ALIVE` avant la fermeture du socket.
- Décodage des noms de Cues encodés en URL afin de restituer correctement les caractères accentués à l'affichage et lors de la sauvegarde.
- Estimation du temps de restauration et mesure du temps réel, y compris l'arrêt des threads et la fermeture de la connexion.

## V9 — Arrêt propre de la connexion

- Mise en place d'un arrêt coopératif des threads d'observation et d'envoi périodique `ALIVE`.
- Attente de la terminaison des threads avant la fermeture du socket.
- Ajout d'une fermeture de secours en cas de thread qui ne s'arrête pas normalement.
- Cette évolution vise à éviter l'erreur socket `WinError 10053` observée lors de la fermeture de la connexion.

## V8 — Vérification du Show et des Cues

- Ajout d'une demande `SHOWLIST` avant l'envoi des paramètres.
- Comparaison du nom du Show sélectionné avec la liste renvoyée par la console.
- Arrêt préventif si le Show cible est absent.
- Ajout d'une vérification finale `CUELIST` pour comparer les Cues attendus avec les noms présents sur la console.
- Centralisation des réponses de listes reçues par le thread d'observation afin que le thread principal puisse les traiter.

## V7 — Base de restauration exhaustive

- Lecture des fichiers d'export `.uicue`.
- Envoi exhaustif des paramètres avec `SETD`, en conservant leur ordre dans le fichier.
- Enregistrement de chaque Cue dans le Show cible avec `SAVECUE`.
- Conservation de la distinction entre les paramètres retenus pour l'affichage et les commandes exhaustives utilisées pour la restauration.
- Affichage de la progression pendant l'envoi des commandes.

---

Les versions décrites ici correspondent aux principales étapes du développement et aux fonctions ajoutées au fil des essais. Elles ne constituent pas un historique détaillé de chaque modification du code.
