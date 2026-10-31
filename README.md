[English version](Readme_EN.md)
# RestoreCUE

## Outil de restauration des Cues pour Soundcraft, testé sur Ui24R

## Compatibilité

**Console :** Soundcraft Ui24R

**Firmware public de référence :**  
Ui24R Firmware v3.5.8328

**Systèmes informatiques :**
- Windows 10 / 11
- Linux (notamment Linux Mint)

**Communication :**  
WebSocket / protocole Socket.IO

Les essais de restauration ont été réalisés sur une console Ui24R réelle.

**Auteur et développeur :** Patrick ARNAUD  
**Version :** V10  
**Année :** 2026

---

## Présentation

RestoreCUE est un logiciel indépendant développé en Python permettant de reconstruire et de restaurer les Cues d'une console Soundcraft Ui24R à partir de fichiers d'export individuels `.uicue`.

Ces fichiers correspondent aux Cues exportés depuis un Show et contiennent les paramètres nécessaires à leur reconstruction.

Le projet est né d'un besoin concret : pouvoir retrouver et reconstruire les Cues d'un Show à partir des fichiers d'une sauvegarde réalisée sur clé USB, sans devoir les recréer manuellement.

La clé USB contenant la sauvegarde doit être connectée à l'ordinateur afin que le programme puisse accéder aux fichiers d'export.

RestoreCUE communique directement avec la console par WebSocket en utilisant les commandes de son interface de contrôle.

## Fonctionnalités

- Connexion à la console à l'aide de son adresse IP.
- Recherche automatique des dossiers contenant des fichiers `.uicue`, notamment sur une clé USB.
- Sélection du dossier correspondant au Show par numéro, sans saisie manuelle du chemin d'accès.
- Affichage de la liste des Cues disponibles.
- Restauration de tous les Cues ou sélection individuelle.
- Sélection par plages de numéros (exemple : `1-10` ou `11-20`).
- Lecture exhaustive des commandes des fichiers `.uicue`.
- Envoi de tous les paramètres dans leur ordre d'origine.
- Vérification préalable de la présence du Show sur la console.
- Enregistrement de chaque Cue dans le Show cible.
- Vérification finale de la présence des Cues sur la console.
- Barre de progression et estimation du temps de restauration.
- Gestion des connexions et arrêt propre des threads.

## Fonctionnement général

Pour restaurer un Show, le programme :

1. Recherche les dossiers contenant les fichiers `.uicue`.
2. Permet de sélectionner le dossier correspondant au Show.
3. Affiche la liste des Cues et propose une sélection.
4. Vérifie la présence du Show sur la console avec `SHOWLIST`.
5. Envoie les paramètres de chaque Cue avec les commandes `SETD`, en conservant leur ordre d'origine.
6. Enregistre chaque Cue dans le Show cible avec `SAVECUE`.
7. Vérifie les noms des Cues présents sur la console avec `CUELIST`.

> [!WARNING]
> RestoreCUE n'utilise jamais la commande `LOADCUE`.
>
> Les commandes `SETD` modifient les paramètres du mix actif pendant la reconstruction. Il est donc indispensable de réaliser une sauvegarde préalable et de tester d'abord le programme sur un Show de test.
>
> Le Show cible doit déjà exister sur la console. Si le Show recherché est absent, la restauration est interrompue avant l'envoi des commandes de modification.

## Installation

RestoreCUE fonctionne sous :
- Windows 10 / 11
- Linux (notamment Linux Mint)

> [!NOTE]
> Python 3 doit être installé.
>
> Le programme utilise uniquement les bibliothèques standard de Python et ne nécessite pas d'interface graphique particulière.

## Utilisation

1. Connecter l'ordinateur au réseau de la Ui24R, de préférence par câble Ethernet (RJ45).
2. Lancer le programme avec la commande correspondant au système utilisé :
	- Windows : `python V10RestoreCUE.py`
	- Linux Mint : `python3 V10RestoreCUE.py`
3. Vérifier l'adresse IP de la console.
4. Sélectionner le dossier du Show.
5. Visualiser les Cues disponibles.
6. Appuyer sur `E` pour lancer la restauration.
7. Choisir les Cues à restaurer ou appuyer sur Entrée pour tous les restaurer.

Un bilan final indique le nombre de Cues attendus, retrouvés et manquants.

> [!TIP]
> Il est possible de restaurer progressivement un Show comportant de nombreux Cues.
>
> Par exemple : sélectionner `1-10`, puis `11-20`, et ainsi de suite.

## Documentation

Les documents détaillés sont disponibles dans le dossier `docs` :

- [Fonctionnement technique](docs/Fonctionnement.md)
- [Tests et validations](docs/Tests_et_Validations.md)

## Tests réalisés

Le programme a été testé sur une console Soundcraft Ui24R réelle, connectée à un ordinateur sous Windows et Linux Mint.

Les essais ont été réalisés avec une connexion Ethernet filaire (RJ45). Le fonctionnement en Wi-Fi n'a pas fait l'objet de tests de validation.

Exemples de tests effectués :

- Restauration complète de 41 Cues : 41 retrouvés.
- Restauration partielle de 10 Cues : 10 retrouvés.
- Restauration de 2 Cues : 2 retrouvés.
- Vérification de l'existence du Show avant restauration.
- Vérification finale de la liste des Cues.
- Vérification de l'arrêt propre des threads et de la fermeture du socket.

> [!CAUTION]
> La vérification `CUELIST` confirme la présence des noms des Cues attendus sur la console.
>
> Elle ne constitue pas une vérification individuelle de l'intégrité de toutes les valeurs des paramètres restaurés. Une vérification complémentaire sur la console reste recommandée.

## Avertissement

> [!WARNING]
> RestoreCUE est un projet indépendant, non affilié, approuvé ou sponsorisé par Soundcraft ou Harman International.
>
> Soundcraft et Ui24R sont des marques appartenant à leurs titulaires respectifs.
>
> Le logiciel est fourni sans garantie. L'utilisateur reste responsable de ses sauvegardes et de ses opérations sur la console.

## Licence et droits d'auteur

RestoreCUE V10 est distribué sous licence MIT.

Copyright (c) 2026 Patrick ARNAUD.

Vous êtes libre d'utiliser, copier, modifier et redistribuer ce logiciel, y compris à des fins commerciales, sous réserve de conserver les mentions de copyright et le texte de la licence dans les copies ou parties substantielles du logiciel.

Consultez le fichier [LICENSE](LICENSE) pour lire le texte intégral de la licence.

## Dépôt e-Soleau – INPI

Le projet RestoreCUE V10 et ses documents associés ont fait l'objet d'un dépôt e-Soleau auprès de l'Institut national de la propriété industrielle (INPI), afin d'établir une preuve datée de leur existence et de leur contenu.

Dépôt effectué le : [31/10/2026]