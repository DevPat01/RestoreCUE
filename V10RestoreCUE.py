#!/usr/bin/env python3

# ============================================================
# RestoreCUE V10 - Soundcraft Ui24R
# Copyright (C) 2026 Patrick ARNAUD
#
# Auteur et développeur du projet : Patrick ARNAUD
#
# Toute redistribution doit conserver les mentions
# de copyright et la licence d'origine.
# Voir le fichier LICENSE pour plus de détails
# ============================================================
# RestoreCUE V10 - Soundcraft Ui24R
# Copyright (c) 2026 Patrick ARNAUD
# Licensed under the MIT License.
# See the LICENSE file in the project root for details.
# ============================================================

import os     #Génère une clé de masquage aléatoire pour les trames WebSocket
import struct # Décode et encode la longueur des trames
import socket
import base64
import hashlib
import http.client
import time
import re
import ipaddress
import threading # lire les messages reçus de l'UI24R
import queue
import select
from pathlib import Path
from urllib.parse import unquote

VERROU_ENVOI = threading.Lock() # verrou pour valider l'envoi complet des trames asynchrones

# Les réponses SHOWLIST et CUELIST sont récupérées par le thread
# observateur, puis consommées par le thread principal.
REPONSES_LISTES = queue.Queue()
DELAI_REPONSE_LISTE = 10.0

# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_HOST = "10.10.2.1"
HOST = DEFAULT_HOST
PORT = 80

DRY_RUN = False

DELAY_BETWEEN_PARAMS = 0.001  #Délai entre l'envoi des SETD pas d'info de soundcraft
DELAY_AFTER_CUE = 0.3         #Délai pour que la console enregistre les paramètres
                              #du CUE, après test de l'ordre de 100ms, mis à 300ms pour etre large
TEMPS_ARRET_ESTIME = 0.5      # Marge prévue pour l'arrêt des threads et du socket

# ============================================================
# SAISIE DE L'ADRESSE IP
# Permet de saisir l'adresse IP de l'UI24R 
# ============================================================

def demander_adresse_ip():

    while True:

        saisie = input(f"Adresse IP du Ui24R [{DEFAULT_HOST}] : ").strip()

        if not saisie:
            return DEFAULT_HOST

        try:
            return str(ipaddress.IPv4Address(saisie))

        except ipaddress.AddressValueError:

            print()
            print("Adresse IP invalide.")
            print("Exemple : 10.10.2.1")
            print("Veuillez recommencer.")
            print()


# ============================================================
# MÉMORISATION DE L'IP DANS LE FICHIER PYTHON
# Si IP différente, a mémorise pour la prochaine connection
# ============================================================

def memoriser_adresse_ip(adresse):

    fichier = Path(__file__).resolve()

    try:

        source = fichier.read_text(encoding="utf-8")
        motif = r"""(?m)^DEFAULT_HOST\s*=\s*["'][^"']*["']\s*$"""
        nouvelle_ligne = f'DEFAULT_HOST = "{adresse}"'

        nouveau_source, nombre = re.subn(motif, lambda m: nouvelle_ligne, source, count=1)

        if nombre != 1:

            print()
            print("ATTENTION : ligne DEFAULT_HOST introuvable.")
            return False

        if nouveau_source == source:
            return True

        fichier.write_text(nouveau_source, encoding="utf-8")

        print()
        print("Adresse IP mémorisée dans le fichier Python.")

        return True

    except OSError as erreur:

        print()
        print("ATTENTION : impossible de mémoriser l'adresse IP.")
        print(erreur)
        print("L'adresse reste utilisable pour cette session.")

        return False


# ============================================================
# FILTRE DES PARAMÈTRES
# ============================================================

def parametre_utile(cle):

    # GAINS MATÉRIELS DES ENTRÉES (hw.1.gain, hw.2.gain, etc.)
    # La valeur est conservée telle quelle, sans conversion.

    if re.fullmatch(r"hw\.\d+\.gain", cle):
        return True

    # VCA 1 À 6 (indices 0 À 5) : mute et niveau (mix)

    if re.fullmatch(r"v\.[0-5]\.(mute|mix)", cle):
        return True

    # PARAMÈTRES DES CANAUX

    if re.fullmatch(r"[iplp]\.\d+\.(mute|pan|mix|solo)", cle):
        return True

    # SENDS DES CANAUX VERS FX 1-4

    if re.fullmatch(r"[iplp]\.\d+\.fx\.[0-3]\.(post|mute|value)", cle):
        return True

    # PARAMÈTRES GLOBAUX FX 1-4

    if re.fullmatch(r"f\.[0-3]\.(mute|pan|mix)", cle):
        return True

    # PARAMÈTRES MAÎTRES DES AUX 1-10

    if re.fullmatch(r"a\.\d+\.(mute|pan|mix)", cle):
        return True

    # ENVOIS AUX VERS MTX (MATRIX)

    if re.fullmatch(r"a\.\d+\.mtx\.\d+\.(mute|pan|value)", cle):
        return True

    # SENDS DES CANAUX, PLAYER, LINE IN ET RETOURS FX VERS AUX 1-10
    # Niveau, mute, pan, pré/post et post-proc si présent

    if re.fullmatch(r"[iplpf]\.\d+\.aux\.\d+\.(post|mute|value|pan|postproc)", cle):
        return True

    return False


# ============================================================
# LECTURE DES FICHIERS .UICUE
# Lit le contenu d'un fichier UICUE, lignes# non retenu
# ============================================================

def lire_cue(chemin):

    params = {}

    with open(chemin, "r", encoding="utf-8", errors="replace") as fichier:

        for ligne in fichier:

            ligne = ligne.strip()

            if not ligne:
                continue

            if ligne.startswith("#"):
                continue

            # Format clé=valeur utilisé dans les exports .UICUE
            if "=" in ligne:
                cle, valeur = ligne.split("=", 1)
                cle = cle.strip()
                valeur = valeur.strip()
                if parametre_utile(cle):
                    params[cle] = valeur
                continue

            # Accepte aussi les lignes de commande Ui24R SETD^clé^valeur
            # si un export ou un fichier intermédiaire les contient.
            resultat = re.fullmatch(r"3:::SETD\^([^\^]+)\^(.+)", ligne)
            if resultat:
                cle, valeur = resultat.groups()
                if parametre_utile(cle):
                    params[cle] = valeur

    return params


# ============================================================
# LECTURE EXHAUSTIVE POUR RESTAURATION
# Envoi de scommandes SETD sans vériication des valeurs.
# En effet le sICUES font tous la même longueur et l'IU24R
# mémorise tous les paramètres, donc on remet tout.
# Exemple : un auxiliaire peut ne pas être utilisé sur un ICUE
# et l'être sur un autre
# ============================================================

def lire_commandes_cue(chemin):
    """Lit les paramètres du cue dans l'ordre du fichier, sans filtre de clé."""
    commandes = []

    with open(chemin, "r", encoding="utf-8", errors="replace") as fichier:
        for numero_ligne, ligne in enumerate(fichier, start=1):
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#"):
                continue

            # Format export : cle=valeur
            if "=" in ligne:
                cle, valeur = ligne.split("=", 1)
                cle, valeur = cle.strip(), valeur.strip()
                if cle:
                    commandes.append((cle, valeur, numero_ligne))
                else:
                    print(f"AVERTISSEMENT ligne {numero_ligne} : clé vide, ignorée.")
                continue

            # Si le fichier contient déjà une commande SETD, la décomposer
            # pour la renvoyer dans le même format sans filtrer sa clé.
            resultat = re.fullmatch(r"3:::SETD\^([^\^]+)\^(.*)", ligne)
            if resultat:
                cle, valeur = resultat.groups()
                commandes.append((cle, valeur, numero_ligne))
                continue

            print(f"AVERTISSEMENT ligne {numero_ligne} : ligne non reconnue, conservée dans le fichier mais non envoyée : {ligne}")

    return commandes




# ============================================================
# CONVERSION DES NIVEAUX EN POURCENTAGE
# afind efaciliter l'affichage en language plus lisible
# ============================================================

def formater_pourcentage(valeur):

    try:
        return f"{float(valeur) * 100:.1f} %"

    except (ValueError, TypeError):
        return valeur


# ============================================================
# AFFICHAGE DU PAN
# ============================================================

def formater_pan(valeur):

    try:
        pan = float(valeur)

    except (ValueError, TypeError):
        return str(valeur)

    pan = max(0.0, min(1.0, pan))

    centre = 0.5
    tolerance = 0.005

    if abs(pan - centre) <= tolerance:
        return f"CENTRE (0 %) [{pan:.3f}]"

    elif pan < centre:

        pourcent = (pan - centre) / centre * 100
        return f"GAUCHE ({pourcent:.0f} %) [{pan:.3f}]"

    else:

        pourcent = (pan - centre) / (1.0 - centre) * 100
        return f"DROITE (+{pourcent:.0f} %) [{pan:.3f}]"


# ============================================================
# AFFICHAGE LISIBLE DES PARAMÈTRES
# ============================================================

def afficher_parametres(nom_cue, params):

    print()
    print("=" * 70)
    print(f"CUE : {nom_cue}")
    print("=" * 70)
    print()

    params_canaux = []
    params_vca = []
    gains_entree = []
    envois_fx = []
    envois_aux = {}
    params_fx = []
    params_aux_master = []
    envois_mtx = []

    for cle, valeur in sorted(params.items()):

        # VCA 1 À 6

        resultat = re.fullmatch(r"v\.([0-5])\.(mute|mix)", cle)

        if resultat:
            vca = int(resultat.group(1)) + 1
            param = resultat.group(2)

            if param == "mute":
                etat = "ON" if valeur == "1" else "OFF"
                params_vca.append(f"VCA{vca} : MUTE {etat}")
            elif param == "pan":
                params_vca.append(f"VCA{vca} : PAN {formater_pan(valeur)}")
            elif param == "mix":
                params_vca.append(f"VCA{vca} : NIVEAU {formater_pourcentage(valeur)}")
            continue

        # GAINS MATÉRIELS DES ENTRÉES

        resultat = re.fullmatch(r"hw\.(\d+)\.gain", cle)

        if resultat:
            canal = int(resultat.group(1))
            gains_entree.append(f"Canal {canal:2d} : gain matériel = {valeur}")
            continue

        # PARAMÈTRES DES CANAUX

        resultat = re.fullmatch(r"([iplp])\.(\d+)\.(mute|pan|mix|solo)", cle)

        if resultat:

            source = resultat.group(1)
            index = int(resultat.group(2))
            canal = index + 1
            if source == "l":
                nom_source = f"LINE IN {'gauche' if index == 0 else 'droite'}"
            elif source == "p":
                nom_source = f"PLAYER {'gauche' if index == 1 else 'droite'}"
            else:
                nom_source = f"Canal {canal:2d}"
            param = resultat.group(3)

            if param == "mute":

                etat = "MUTE : ON" if valeur == "1" else "MUTE : OFF"
                params_canaux.append(f"{nom_source} : {etat}")

            elif param == "pan":

                params_canaux.append(f"{nom_source} : PAN {formater_pan(valeur)}")

            elif param == "mix":

                params_canaux.append(f"{nom_source} : NIVEAU {formater_pourcentage(valeur)}")

            elif param == "solo":

                etat = "SOLO : ON" if valeur == "1" else "SOLO : OFF"
                params_canaux.append(f"{nom_source} : {etat}")

            continue

        # SENDS CANAUX VERS FX

        resultat = re.fullmatch(r"([iplp])\.(\d+)\.fx\.([0-3])\.(post|mute|value)", cle)

        if resultat:

            source = resultat.group(1)
            index = int(resultat.group(2))
            canal = index + 1
            if source == "l":
                nom_source = f"LINE IN {'gauche' if index == 0 else 'droite'}"
            elif source == "p":
                nom_source = f"PLAYER {'gauche' if index == 1 else 'droite'}"
            else:
                nom_source = f"Canal {canal:2d}"
            fx = int(resultat.group(3)) + 1
            param = resultat.group(4)

            if param == "value":

                envois_fx.append(f"{nom_source} -> FX{fx} : niveau {formater_pourcentage(valeur)}")

            elif param == "mute":

                etat = "MUTE : ON" if valeur == "1" else "MUTE : OFF"
                envois_fx.append(f"{nom_source} -> FX{fx} : {etat}")

            elif param == "post":

                etat = "POST" if valeur == "1" else "PRE"
                envois_fx.append(f"{nom_source} -> FX{fx} : {etat}")

            continue

        # SENDS VERS AUX 1-10 (CANAUX, PLAYER, LINE IN ET RETOURS FX)

        resultat = re.fullmatch(r"([iplpf])\.(\d+)\.aux\.(\d+)\.(post|mute|value|pan|postproc)", cle)

        if resultat:

            source = resultat.group(1)
            index = int(resultat.group(2))
            if source == "l":
                nom_source = f"LINE IN {'gauche' if index == 0 else 'droite'}"
            elif source == "p":
                nom_source = f"PLAYER {'gauche' if index == 1 else 'droite'}"
            elif source == "f":
                nom_source = f"Retour FX{index + 1}"
            else:
                nom_source = f"Canal {index + 1:2d}"
            aux = int(resultat.group(3)) + 1
            param = resultat.group(4)

            cle_envoi = (nom_source, aux)
            envoi = envois_aux.setdefault(cle_envoi, {})
            envoi[param] = valeur
            continue

        # PARAMÈTRES MAÎTRES DES AUX 1-10

        resultat = re.fullmatch(r"a\.(\d+)\.(mute|pan|mix)", cle)

        if resultat:
            aux = int(resultat.group(1)) + 1
            param = resultat.group(2)
            if param == "mix":
                params_aux_master.append(f"AUX{aux} : NIVEAU {formater_pourcentage(valeur)}")
            elif param == "pan":
                params_aux_master.append(f"AUX{aux} : PAN {formater_pan(valeur)}")
            elif param == "mute":
                etat = "ON" if valeur == "1" else "OFF"
                params_aux_master.append(f"AUX{aux} : MUTE {etat}")
            continue

        # ENVOIS AUX VERS MTX (MATRIX)

        resultat = re.fullmatch(r"a\.(\d+)\.mtx\.(\d+)\.(mute|pan|value)", cle)

        if resultat:
            aux = int(resultat.group(1)) + 1
            mtx = int(resultat.group(2)) + 1
            param = resultat.group(3)
            if param == "value":
                envois_mtx.append(f"AUX{aux} -> MTX{mtx} : niveau {formater_pourcentage(valeur)}")
            elif param == "pan":
                envois_mtx.append(f"AUX{aux} -> MTX{mtx} : PAN {formater_pan(valeur)}")
            else:
                etat = "ON" if valeur == "1" else "OFF"
                envois_mtx.append(f"AUX{aux} -> MTX{mtx} : MUTE {etat}")
            continue

        # PARAMÈTRES GLOBAUX FX

        resultat = re.fullmatch(r"f\.([0-3])\.(mute|pan|mix)", cle)

        if resultat:

            fx = int(resultat.group(1)) + 1
            param = resultat.group(2)

            if param == "mute":

                etat = "MUTE : ON" if valeur == "1" else "MUTE : OFF"
                params_fx.append(f"FX{fx} : {etat}")

            elif param == "pan":

                params_fx.append(f"FX{fx} : PAN {formater_pan(valeur)}")

            elif param == "mix":

                params_fx.append(f"FX{fx} : MIX {formater_pourcentage(valeur)}")

    # AFFICHAGE

    if gains_entree:
        print("GAINS MATÉRIELS DES ENTRÉES")
        print("-" * 40)
        for ligne in gains_entree:
            print("  " + ligne)
        print()

    if params_vca:
        print("PARAMÈTRES DES VCA (1 À 6)")
        print("-" * 40)
        for ligne in params_vca:
            print("  " + ligne)
        print()

    if params_canaux:

        print("PARAMÈTRES DES CANAUX")
        print("-" * 40)

        for ligne in params_canaux:
            print("  " + ligne)

        print()

    if envois_fx:

        print("SENDS VERS FX")
        print("-" * 40)

        for ligne in envois_fx:
            print("  " + ligne)

        print()

    if envois_aux:

        print("SENDS VERS AUX 1-10")
        print("-" * 40)

        for (nom_source, aux), envoi in sorted(envois_aux.items(), key=lambda item: (item[0][1], item[0][0])):
            morceaux = []
            if "value" in envoi:
                morceaux.append("niveau " + formater_pourcentage(envoi["value"]))
            if "mute" in envoi:
                morceaux.append("MUTE " + ("ON" if envoi["mute"] == "1" else "OFF"))
            if "pan" in envoi:
                morceaux.append("PAN " + formater_pan(envoi["pan"]))
            if "post" in envoi:
                morceaux.append("POST" if envoi["post"] == "1" else "PRE")
            if "postproc" in envoi:
                morceaux.append("POST PROC " + ("OFF" if envoi["postproc"] == "1" else "ON"))
            print(f"  {nom_source} -> AUX{aux} : " + " | ".join(morceaux))

        print()

    if params_aux_master:

        print("PARAMÈTRES MAÎTRES DES AUX")
        print("-" * 40)
        for ligne in params_aux_master:
            print("  " + ligne)
        print()

    if envois_mtx:

        print("ENVOIS AUX VERS MTX (MATRIX)")
        print("-" * 40)
        for ligne in envois_mtx:
            print("  " + ligne)
        print()

    if params_fx:

        print("PARAMÈTRES GLOBAUX FX")
        print("-" * 40)

        for ligne in params_fx:
            print("  " + ligne)

        print()

    print(f"Total : {len(params)} paramètres retenus")
    print()
    print("-" * 70)

# ============================================================
# OBSERVATION DES MESSAGES WEBSOCKET ENTRANTS
# Observation de ce qui entre notamment pour répondre 
# aux 2:: par un 2:: qui permet de valider la présence du client
# ============================================================

def lire_exactement(sock, longueur, stop_event=None):
    """Lit exactement le nombre d'octets demandé.

    Avec stop_event, vérifie régulièrement si l'arrêt est demandé.
    Cela permet au thread observateur de quitter sans fermer le socket
    depuis un autre thread pendant un recv() bloquant.
    """
    donnees = bytearray()

    while len(donnees) < longueur:
        if stop_event is not None:
            if stop_event.is_set():
                return None

            lisible, _, _ = select.select([sock], [], [], 0.25)
            if not lisible:
                continue

        bloc = sock.recv(longueur - len(donnees))

        if not bloc:
            return None

        donnees.extend(bloc)

    return bytes(donnees)


def lire_trame_websocket(sock, stop_event=None):
    """Lit une trame WebSocket complète, avec arrêt coopératif facultatif."""
    entete = lire_exactement(sock, 2, stop_event)

    if entete is None:
        return None

    premier, second = entete
    fin = bool(premier & 0x80)
    opcode = premier & 0x0F
    masque = bool(second & 0x80)
    longueur = second & 0x7F
    # print(
        # f"[TRAME] premier=0x{premier:02X}, "
        # f"second=0x{second:02X}, opcode={opcode}, "
        # f"fin={fin}, longueur_initiale={longueur}"
    # )
    if longueur == 126:
        donnees = lire_exactement(sock, 2, stop_event)
        if donnees is None:
            return None
        longueur = struct.unpack("!H", donnees)[0]

    elif longueur == 127:
        donnees = lire_exactement(sock, 8, stop_event)
        if donnees is None:
            return None
        longueur = struct.unpack("!Q", donnees)[0]

    # Protection contre une longueur de trame anormale.
    if longueur > 16 * 1024 * 1024:
        raise ValueError(
            f"Trame WebSocket trop grande : {longueur} octets"
        )

    cle = None

    if masque:
        cle = lire_exactement(sock, 4, stop_event)
        if cle is None:
            return None

    charge = lire_exactement(sock, longueur, stop_event)

    if charge is None:
        return None

    if masque:
        charge = bytes(
            octet ^ cle[i % 4]
            for i, octet in enumerate(charge)
        )

    return fin, opcode, charge


def envoyer_trame_websocket(sock, opcode, charge=b""):
    """Envoie une trame WebSocket masquée, comme l'exige le client."""
    if isinstance(charge, str):
        charge = charge.encode("utf-8")

    longueur = len(charge)
    entete = bytearray([0x80 | opcode])

    if longueur < 126:
        entete.append(0x80 | longueur)
    elif longueur < 65536:
        entete.append(0x80 | 126)
        entete.extend(struct.pack("!H", longueur))
    else:
        entete.append(0x80 | 127)
        entete.extend(struct.pack("!Q", longueur))

    cle = os.urandom(4)
    entete.extend(cle)

    masque = bytes(
        octet ^ cle[i % 4]
        for i, octet in enumerate(charge)
    )

    with VERROU_ENVOI:
        sock.sendall(bytes(entete) + masque)


def envoyer_message_socketio(sock, message):
    """Envoie un message Socket.IO sous forme de trame texte."""
    envoyer_trame_websocket(sock, 0x1, message)


def observer_websocket(sock, stop_event):
    """Lit les messages reçus et gère les heartbeats jusqu'à l'arrêt demandé."""
    compteurs = {
        "RTA": 0,
        "VU2": 0,
        "heartbeat_recu": 0,
        "heartbeat_envoye": 0,
        "autres": 0,
    }

    fragments = bytearray()
    opcode_message = None

    print("[OBSERVATION] Lecture WebSocket démarrée.")

    try:
        while not stop_event.is_set():
            trame = lire_trame_websocket(sock, stop_event)

            if trame is None:
                if stop_event.is_set():
                    print("[OBSERVATION] Arrêt demandé, lecture terminée.")
                else:
                    print("[OBSERVATION] Connexion fermée par le pair.")
                break

            fin, opcode, charge = trame

            # Fermeture WebSocket.
            if opcode == 0x8:
                code = None
                raison = ""

                if len(charge) >= 2:
                    code = struct.unpack("!H", charge[:2])[0]
                    raison = charge[2:].decode(
                        "utf-8", errors="replace"
                    )

                print(
                    f"[OBSERVATION] Fermeture reçue : "
                    f"code={code}, raison={raison!r}"
                )
                break

            # PING WebSocket : réponse par PONG WebSocket.
            if opcode == 0x9:
                envoyer_trame_websocket(sock, 0xA, charge)
                print("[OBSERVATION] PING WebSocket reçu, PONG envoyé.")
                continue

            # PONG WebSocket.
            if opcode == 0xA:
                print("[OBSERVATION] PONG WebSocket reçu.")
                continue

            # Début d'un message texte ou binaire.
            if opcode in (0x1, 0x2):
                fragments = bytearray(charge)
                opcode_message = opcode

            # Suite d'un message fragmenté.
            elif opcode == 0x0:
                if opcode_message is None:
                    print(
                        "[OBSERVATION] Fragment sans message initial, "
                        "ignoré."
                    )
                    continue

                fragments.extend(charge)

            else:
                continue

            if not fin:
                continue

            type_message = opcode_message
            contenu = bytes(fragments)

            fragments = bytearray()
            opcode_message = None

            if type_message != 0x1:
                print(
                    f"[OBSERVATION] Message binaire reçu : "
                    f"{len(contenu)} octets."
                )
                continue

            message = contenu.decode("utf-8", errors="replace")
            maintenant = time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"

            # Conserver les réponses de listes demandées par V8.
            # Le thread observateur reste l'unique lecteur du socket.
            if (
                message == "3:::SHOWLIST"
                or message.startswith("3:::SHOWLIST^")
                or message == "3:::CUELIST"
                or message.startswith("3:::CUELIST^")
            ):
                REPONSES_LISTES.put(message)

            # Heartbeat Socket.IO applicatif. C'est ici que l'on teste le 2:: et on répond
            if message == "2::":
                compteurs["heartbeat_recu"] += 1

              #  print(
               #     f"[OBSERVATION {maintenant}] "
               #     f"Heartbeat reçu : {message!r}"
              #  )

                # Essai expérimental : reproduire la réponse observée
                # dans la page web. Une seule réponse par heartbeat reçu.
                envoyer_message_socketio(sock, "2::")
                compteurs["heartbeat_envoye"] += 1

                # print(
                    # f"[OBSERVATION {maintenant}] "
                    # f"Heartbeat envoyé : '2::'"
                # )
                continue

            # Données RTA et VU2.
            if "RTA^" in message:
                compteurs["RTA"] += 1

            if "VU2^" in message:
                compteurs["VU2"] += 1

            if "RTA^" in message or "VU2^" in message:
                pass
            else:
                compteurs["autres"] += 1
                # print(
                    # f"[OBSERVATION {maintenant}] "
                    # f"Autre message : {message[:300]!r}"
                # )

    except (ConnectionError, OSError) as erreur:
        if stop_event.is_set():
            pass  # Arrêt demandé : une interruption de lecture est normale.
        elif getattr(erreur, "winerror", None) == 10038:
            pass  # Socket déjà fermé.
        else:
            print(f"[OBSERVATION] Erreur socket : {erreur}")

    except Exception as erreur:
        print(
            f"[OBSERVATION] Erreur de lecture : "
            f"{type(erreur).__name__}: {erreur}"
        )

    finally:
        print("[OBSERVATION] Bilan :")
        for nom, valeur in compteurs.items():
            print(f"  {nom} = {valeur}")


# ============================================================
# WEBSOCKET
# connexion à la console UI24R
# ============================================================

def connexion_websocket():

    print()
    print(f"Connexion à {HOST}:{PORT}...")

    conn = http.client.HTTPConnection(HOST, PORT, timeout=10)

    try:

        conn.request("GET", "/socket.io/1/")
        reponse = conn.getresponse()
        donnees = reponse.read().decode("utf-8", errors="replace")

    finally:
        conn.close()

    session_id = None

    for ligne in donnees.splitlines():

        ligne = ligne.strip()

        if ":5:5:websocket" in ligne:

            session_id = ligne.split(":")[0]
            break

    if not session_id:
        raise RuntimeError("Impossible de récupérer le session_id Socket.IO.")

    print(f"Session ID : {session_id}")

    # HANDSHAKE WEBSOCKET

    sock = socket.create_connection((HOST, PORT), timeout=10)

    try:

      # cle_brute = hashlib.sha1(f"{time.time()}".encode()).digest()
      # cle = base64.b64encode(cle_brute).decode()
        cle = base64.b64encode(os.urandom(16)).decode("ascii")
        requete = (
            f"GET /socket.io/1/websocket/{session_id} HTTP/1.1\r\n"
            f"Host: {HOST}\r\n"
            f"Upgrade: WebSocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {cle}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"Origin: http://{HOST}\r\n"
            f"\r\n"
        )

        sock.sendall(requete.encode())
        # Lire les en-têtes HTTP sans dépasser leur fin.
        reponse = bytearray()

        while not reponse.endswith(b"\r\n\r\n"):
            octet = sock.recv(1)

            if not octet:
                raise ConnectionError(
                    "Connexion fermée pendant le handshake HTTP."
                )

            reponse.extend(octet)

        reponse = bytes(reponse)
        print(reponse.decode("latin-1", errors="replace"))

        if b"101" not in reponse:
            raise RuntimeError("Échec du handshake WebSocket.")

        print("WebSocket connecté.")
        
        sock.settimeout(None)

        return sock

    except Exception:

        sock.close()
        raise


# ============================================================
# ENVOI WEBSOCKET
# Après des test avec une trame fixe, utilisation trame aléatoire
# comme l'exige le protocole
# ============================================================
def envoyer_websocket(sock, message):
    """Envoie un message texte WebSocket avec un masque aléatoire."""

    envoyer_trame_websocket(sock, 0x1, message)
    



# ============================================================
# COMMANDES UI24R
# ============================================================

def regler_valeur(sock, cle, valeur):

    commande = f"3:::SETD^{cle}^{valeur}"
    envoyer_websocket(sock, commande)
    time.sleep(DELAY_BETWEEN_PARAMS) #paramètre de délay entre l'envoi des SETD, pas d'info sur la vitese de l'UI24R


def sauvegarder_cue(sock, nom_show, nom_cue):  # Enregistre le CUE dans le show cible

    commande = f"3:::SAVECUE^{nom_show}^{nom_cue}"

    print()
    print(f"Sauvegarde du Cue : {nom_cue}")

    envoyer_websocket(sock, commande)
    time.sleep(DELAY_AFTER_CUE)


def vider_reponses_listes():
    """Écarte les anciennes réponses avant une nouvelle demande de liste."""
    while True:
        try:
            REPONSES_LISTES.get_nowait()
        except queue.Empty:
            break


def demander_reponse_liste(sock, commande, debut_reponse, timeout=DELAI_REPONSE_LISTE):
    """Envoie une demande et attend sa réponse, lue par observer_websocket()."""
    vider_reponses_listes()
    envoyer_websocket(sock, commande)

    echeance = time.monotonic() + timeout

    while True:
        restant = echeance - time.monotonic()
        if restant <= 0:
            raise TimeoutError(
                f"Aucune réponse reçue pour {commande!r} après {timeout:.0f} secondes."
            )

        try:
            message = REPONSES_LISTES.get(timeout=restant)
        except queue.Empty:
            raise TimeoutError(
                f"Aucune réponse reçue pour {commande!r} après {timeout:.0f} secondes."
            )

        # Pour CUELIST, le nom du show fait partie de l'en-tête attendu.
        if message == debut_reponse or message.startswith(debut_reponse + "^"):
            return message


def extraire_noms_shows(reponse):
    """Extrait les noms après 3:::SHOWLIST^, dans l'ordre reçu."""
    prefixe = "3:::SHOWLIST"
    if reponse != prefixe and not reponse.startswith(prefixe + "^"):
        raise ValueError(f"Réponse SHOWLIST inattendue : {reponse!r}")

    contenu = reponse[len(prefixe):]
    if contenu.startswith("^"):
        contenu = contenu[1:]

    return [nom for nom in contenu.split("^") if nom]


def extraire_noms_cues(reponse, nom_show):
    """Extrait les noms après 3:::CUELIST^nom_du_show^, dans l'ordre reçu."""
    prefixe = f"3:::CUELIST^{nom_show}"
    if reponse != prefixe and not reponse.startswith(prefixe + "^"):
        raise ValueError(f"Réponse CUELIST inattendue pour {nom_show!r} : {reponse!r}")

    contenu = reponse[len(prefixe):]
    if contenu.startswith("^"):
        contenu = contenu[1:]

    return [nom for nom in contenu.split("^") if nom]


# ============================================================
# RECHERCHE DES CUES
# Permert de trouver le nombre de CUE dans un show
# ============================================================

def trouver_cues(dossier):

    fichiers = sorted(
        (
            chemin for chemin in dossier.iterdir()
            if chemin.is_file()
            and chemin.suffix.casefold() == ".uicue"
        ),
        key=lambda chemin: chemin.name.casefold()
    )
    cues = []

    for chemin in fichiers:

        params = lire_cue(chemin)  # visualisation : uniquement les clés reconnues
        commandes = lire_commandes_cue(chemin)  # restauration : toutes les clés

        cues.append({
            "path": chemin,
            "name": chemin.stem,
            "parameters": params,
            "commands": commandes,
        })

    return cues


# ============================================================
# LISTE DES CUES
# Affichage des infos sur les CUE trouvés
# ============================================================

def afficher_liste_cues(cues, dossier):

    print()
    print("=" * 70)
    print("CUES TROUVÉS")
    print("=" * 70)

    print(f"Dossier : {dossier}")
    print()

    if not cues:

        print("Aucun fichier .uicue trouvé.")
        return

    for numero, cue in enumerate(cues, start=1):
        nom = unquote(cue["name"])
        print(f"{numero:3d} - {nom}   ({len(cue.get('commands', []))} commandes à restaurer ; {len(cue['parameters'])} paramètres visualisés)")

    print()
    print(f"Total : {len(cues)} Cue(s)")


# ============================================================
# VISUALISATION V
# Commande qui pemret de lire les CUE et de vérifier les 
# paramètres avant de restaurer le CUE
# ============================================================

def visualiser_cues(cues):

    if not cues:

        print("Aucun Cue à afficher.")
        input("\nAppuyez sur Entrée pour revenir au menu...")
        return

    for cue in cues:

        afficher_parametres(unquote(cue["name"], encoding="utf-8"),cue["parameters"])
        input("\nAppuyez sur Entrée pour afficher le Cue suivant...")

    print()
    print("Fin de la visualisation.")
    input("\nAppuyez sur Entrée pour revenir au menu...")

# ============================================================
# BARRE DE PROGRESSION
# afficahge d'une barre de progression pendant la restauration
# d'un CUE
# ============================================================

def afficher_progression(numero_cue, total_cues, nom_cue, index, total):
    largeur = 30
    pourcentage = index / total if total else 1
    remplissage = int(largeur * pourcentage)
    barre = "█" * remplissage + "░" * (largeur - remplissage)

    print(
        f"\rCue {numero_cue}/{total_cues} | {nom_cue[:30]:30s} "
        f"[{barre}] {pourcentage * 100:5.1f}% "
        f"({index}/{total})",
        end="",
        flush=True,
    )
    
# ============================================================
# affichage durée
#
# ============================================================

def formater_duree(secondes):
    secondes = int(round(secondes))
    minutes, secondes = divmod(secondes, 60)

    if minutes:
        return f"{minutes} min {secondes} s"
    return f"{secondes} s"
    
# ============================================================
# Envoyer ALIVE toutes les secondes
# Validation présence à la console
# ============================================================

def envoyer_alive(sock, stop_event):
    """Envoie ALIVE chaque seconde et s'arrête proprement sur événement."""
    while not stop_event.is_set():
        try:
            envoyer_websocket(sock, "3:::ALIVE")
        except (ConnectionError, OSError) as erreur:
            if not stop_event.is_set():
                print(f"[ALIVE] Erreur socket : {erreur}")
            break

        # wait() se réveille immédiatement quand l'arrêt est demandé.
        if stop_event.wait(1.0):
            break


def arreter_threads_socket(sock, stop_event, threads):
    """Arrête les threads avant de fermer la connexion TCP."""
    stop_event.set()

    # Le lecteur utilise select() avec une attente maximale de 0,25 s ;
    # il peut donc quitter sans qu'on ferme le socket sous ses pieds.
    for thread in threads:
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    threads_actifs = [
        thread.name for thread in threads
        if thread is not None and thread.is_alive()
    ]

    # Sécurité exceptionnelle : si un thread n'a pas quitté, shutdown()
    # débloque les opérations socket avant la fermeture finale.
    if threads_actifs:
        print(
            "[ARRÊT] Thread(s) encore actif(s) : "
            + ", ".join(threads_actifs)
            + ". Interruption de secours du socket."
        )
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        for thread in threads:
            if thread is not None and thread.is_alive():
                thread.join(timeout=1.0)

    encore_actifs = [
        thread.name for thread in threads
        if thread is not None and thread.is_alive()
    ]
    if encore_actifs:
        print(
            "[ARRÊT] Attention : thread(s) non arrêtés : "
            + ", ".join(encore_actifs)
        )
    else:
        print("[ARRÊT] Threads d'observation et ALIVE arrêtés.")

# ============================================================
# RECONSTRUCTION CUES
# ============================================================

def reconstruire_cues(cues, nom_show):

    if not cues:

        print("Aucun Cue à reconstruire.")
        return

    print()
    print("=" * 70)
    print("RECONSTRUCTION DES CUES")
    print("=" * 70)

    print()
    print(f"Show : {nom_show}")
    print(f"Cues : {len(cues)}")
    print()

    print("ATTENTION :")
    print("Cette opération va modifier les Cues présents dans le Ui24R.")

    print()
    print("Les fichiers .uicue originaux ne seront PAS modifiés.")
    print("LOADCUE ne sera JAMAIS exécuté.")
    print()

    confirmation = input("Taper OUI pour continuer : ").strip()

    if confirmation != "OUI":

        print()
        print("Opération annulée.")
        return

    sock = None
    nombre_cues = len(cues)

    nombre_parametres = len(cues[0]["commands"]) if cues else 0
    nombre_parametres_total = nombre_parametres * nombre_cues

    # Temps théorique basé sur les délais programmés
    temps_theorique = nombre_parametres_total * DELAY_BETWEEN_PARAMS + nombre_cues * DELAY_AFTER_CUE
   
   # Marge de sécurité de 65% pour les échanges réseau et les heartbeats
    temps_estime = temps_theorique * 1.65 + TEMPS_ARRET_ESTIME

    minutes = int(temps_estime // 60)
    secondes = int(round(temps_estime % 60))

    print("\n========== RESTAURATION DES CUES ==========")
    print(f"Nombre de cues       : {nombre_cues}")
    print(f"Paramètres par cue   : {nombre_parametres}")
    print(f"Paramètres estimés   : {nombre_parametres_total:,}".replace(",", " "))
    print(f"Temps estimé         : {minutes} min {secondes} s")
    print("============================================\n")
    debut_restauration = time.monotonic()

    stop_event = threading.Event()
    thread_observation = None
    thread_alive = None

    try:

        sock = connexion_websocket()
        print()

        thread_observation = threading.Thread(
            target=observer_websocket,
            args=(sock, stop_event),
            name="Ui24R-observation",
            daemon=True,
        )
        thread_observation.start()

        thread_alive = threading.Thread(
            target=envoyer_alive,
            args=(sock, stop_event),
            name="Ui24R-alive",
            daemon=True,
        )
        thread_alive.start()

        # CONTRÔLE PRÉALABLE : le show cible doit déjà exister.
        print()
        print("Vérification de la présence du show sur la console...")
        reponse_shows = demander_reponse_liste(
            sock,
            "3:::SHOWLIST",
            "3:::SHOWLIST",
        )
        shows_console = extraire_noms_shows(reponse_shows)

        if nom_show not in shows_console:
            print()
            print("ERREUR : le show cible n'existe pas sur la console.")
            print(f"Show recherché : {nom_show}")
            print("Shows trouvés :")
            if shows_console:
                for nom in shows_console:
                    print(f"  - {nom}")
            else:
                print("  (aucun show retourné)")
            print()
            print("AUCUNE commande SETD ni SAVECUE n'a été envoyée.")
            return

        print(f"Show confirmé sur la console : {nom_show}")

        for numero, cue in enumerate(cues, start=1):
            nom_cue = unquote(cue["name"], encoding="utf-8")
            print()
            print("=" * 70)
            print(f"[{numero}/{len(cues)}] Reconstruction : {nom_cue}")
            print("=" * 70)

            commandes = cue.get("commands")
            if commandes is None:
                commandes = [(cle, valeur, 0) for cle, valeur in cue["parameters"].items()]

            print(f"{len(commandes)} commandes à envoyer, dans l'ordre du fichier, sans filtre de clé.")

            # ENVOI EXHAUSTIF : la visualisation ne filtre pas la restauration.

            for index, (cle, valeur, numero_ligne) in enumerate(commandes, start=1):

                if not DRY_RUN:
                    regler_valeur(sock, cle, valeur)

                # Actualiser l'affichage toutes les 25 commandes et à la fin.
                if index % 25 == 0 or index == len(commandes):
                    afficher_progression(numero, len(cues), nom_cue, index, len(commandes))

            print()  # Passer à la ligne après la barre de progression.


            # SAUVEGARDE DU CUE
            nom = unquote(cue["name"])
            if DRY_RUN:
                
                print(f"DRY RUN : SAVECUE^{nom_show}^{nom}")

            else:
                sauvegarder_cue(sock, nom_show, nom)

            print()
            print(f"Cue '{nom}' reconstruit.")

        print()
        print("=" * 70)
        print("RECONSTRUCTION DES CUES TERMINÉE")
        print("=" * 70)

        # CONTRÔLE FINAL : relire la liste réelle des cues dans le show.
        if DRY_RUN:
            print()
            print("DRY RUN : aucun SAVECUE n'a été effectué.")
            print("Le contrôle final de présence des cues est donc ignoré.")
            nombre_cues_presents = None
            nombre_cues_manquants = None
        else:
            print()
            print("Vérification des cues présents dans le show...")
            commande_cuelist = f"3:::CUELIST^{nom_show}"
            debut_reponse_cuelist = f"3:::CUELIST^{nom_show}"
            reponse_cues = demander_reponse_liste(
                sock,
                commande_cuelist,
                debut_reponse_cuelist,
            )
            noms_cues_console = extraire_noms_cues(reponse_cues, nom_show)

            noms_cues_attendus = [unquote(cue["name"]) for cue in cues]
            noms_cues_presents = set(noms_cues_console)
            cues_manquants = [
                nom for nom in noms_cues_attendus
                if nom not in noms_cues_presents
            ]

            nombre_cues_presents = len(noms_cues_attendus) - len(cues_manquants)
            nombre_cues_manquants = len(cues_manquants)

            print()
            print(f"Cues attendus        : {len(noms_cues_attendus)}")
            print(f"Cues retrouvés       : {nombre_cues_presents}")
            print(f"Cues manquants       : {nombre_cues_manquants}")
            print(f"Cues présents au total dans le show : {len(noms_cues_console)}")

            if cues_manquants:
                print()
                print("ATTENTION : certains cues attendus sont absents de la liste console :")
                for nom in cues_manquants:
                    print(f"  - {nom}")
            else:
                print()
                print("VÉRIFICATION RÉUSSIE : tous les cues attendus figurent dans le show.")

        # --------------------------------------------------------
        # ARRÊT DES THREADS ET FERMETURE DU SOCKET
        # --------------------------------------------------------

        temps_arret = 0.0

        if sock is not None:

            debut_arret = time.monotonic()

            arreter_threads_socket(
                sock,
                stop_event,
                (thread_alive, thread_observation),
            )

            try:
                sock.close()
                print("[CONNEXION] Socket fermé proprement.")

            except OSError as erreur:
                print(f"[CONNEXION] Erreur à la fermeture du socket : {erreur}")

            finally:
                sock = None

            temps_arret = time.monotonic() - debut_arret

        # Le temps réel inclut maintenant la fermeture complète, y compris l'arrêt des daemon
        temps_reel = time.monotonic() - debut_restauration

        minutes = int(temps_reel // 60)
        secondes = int(round(temps_reel % 60))

        # --------------------------------------------------------
        # BILAN FINAL
        # --------------------------------------------------------

        print("\n========== BILAN DE LA RESTAURATION ==========")

        if DRY_RUN:
            print("Mode                 : DRY RUN (aucune sauvegarde)")

        elif nombre_cues_manquants == 0:
            print(f"Cues vérifiés        : {nombre_cues_presents} / {len(cues)}")
            print("Résultat             : SUCCÈS")

        else:
            print(f"Cues vérifiés        : {nombre_cues_presents} / {len(cues)}")
            print("Résultat             : INCOMPLET - voir les cues manquants")

        print(f"Temps estimé         : {formater_duree(temps_estime)}")
        print(f"Temps arrêt threads  : {temps_arret:.2f} s")
        print(f"Temps réel           : {minutes} min {secondes} s")
        print("==============================================") 
    except Exception as erreur:

        print()
        print("=" * 70)
        print("ERREUR")
        print("=" * 70)

        print(erreur)

    finally:

        if sock:
            # Arrêt coopératif et attente de la fin des threads AVANT
            # la fermeture du socket, pour éviter le WinError 10053
            # provoqué par un recv() encore bloqué lors de sock.close().
            arreter_threads_socket(
                sock,
                stop_event,
                (thread_alive, thread_observation),
            )

            try:
                sock.close()
                print("[CONNEXION] Socket fermé proprement.")
            except OSError as erreur:
                print(f"[CONNEXION] Erreur à la fermeture du socket : {erreur}")


# ============================================================
# SÉLECTION DES CUES À RESTAURER
# Entrée = tous les cues
# Accepte les numéros individuels et les plages :
# Exemples : 1-10 / 11-20 / 1-5,8,12-15
# L'ordre original des fichiers est toujours conservé.
# ============================================================

def selectionner_cues(cues):

    if not cues:
        return []

    while True:

        print()
        print("SÉLECTION DES CUES À RESTAURER")
        print("-" * 70)
        print("Entrée seule = restaurer TOUS les cues")
        print("Numéros individuels : 1,3,5")
        print("Plages de numéros    : 1-10")
        print("Sélection mixte      : 1-5,8,12-15")
        print()

        saisie = input("Cues à restaurer : ").strip()

        if not saisie:
            print(f"Tous les cues seront restaurés ({len(cues)}).")
            return list(cues)

        numeros_selectionnes = set()
        morceaux = saisie.split(",")
        erreur = False

        for morceau in morceaux:

            morceau = morceau.strip()

            if not morceau:
                erreur = True
                break

            # Numéro individuel
            if re.fullmatch(r"\d+", morceau):

                debut = fin = int(morceau)

            # Plage de numéros : 1-10
            else:

                resultat = re.fullmatch(r"(\d+)\s*-\s*(\d+)", morceau)

                if not resultat:
                    erreur = True
                    break

                debut = int(resultat.group(1))
                fin = int(resultat.group(2))

                if debut > fin:
                    print(f"Plage incorrecte : {morceau}")
                    erreur = True
                    break

            # Vérification des limites
            if debut < 1 or fin > len(cues):
                print(f"Numéro hors limites : {morceau}")
                print(f"Choisis entre 1 et {len(cues)}.")
                erreur = True
                break

            numeros_selectionnes.update(range(debut, fin + 1))

        if erreur:
            print("Sélection invalide. Recommence.")
            continue

        # Conserver impérativement l'ordre original.
        selection = [
            cue
            for numero, cue in enumerate(cues, start=1)
            if numero in numeros_selectionnes
        ]

        print()
        print(f"{len(selection)} cue(s) sélectionné(s) :")

        for numero, cue in enumerate(cues, start=1):

            if numero in numeros_selectionnes:
                print(f"  {numero:02d} - {unquote(cue['name'])}")

        return selection

# ============================================================
# SÉLECTION DU DOSSIER SHOW
# Recherche récursive des dossiers contenant directement des .uicue
# ============================================================

def trouver_dossiers_shows(racine):
    """Retourne les dossiers contenant au moins un fichier .uicue."""
    racine = Path(racine).expanduser().resolve()
    dossiers = []
    dossiers_a_ignorer = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
    }

    for chemin_courant, sous_dossiers, fichiers in os.walk(racine):
        sous_dossiers[:] = [
            nom for nom in sous_dossiers
            if nom not in dossiers_a_ignorer
        ]

        fichiers_uicue = [
            nom for nom in fichiers
            if nom.lower().endswith(".uicue")
        ]

        if fichiers_uicue:
            dossiers.append((Path(chemin_courant), len(fichiers_uicue)))

    return sorted(
        dossiers,
        key=lambda element: (
            element[0].name.casefold(),
            str(element[0]).casefold(),
        ),
    )


def choisir_dossier_show():
    """Affiche les dossiers .uicue trouvés et retourne celui choisi par numéro."""
    racine_defaut = Path(__file__).resolve().parent

    while True:
        print()
        print("=" * 70)
        print("RECHERCHE DES DOSSIERS DE SHOW")
        print("=" * 70)
        print("Les dossiers contenant des fichiers .uicue seront recherchés")
        print("dans le répertoire indiqué et ses sous-répertoires.")
        print()

        saisie = input(
            f"Répertoire de recherche [{racine_defaut}] (Entrée = défaut) : "
        ).strip()
        racine = Path(saisie).expanduser() if saisie else racine_defaut
        racine = racine.resolve()

        if not racine.is_dir():
            print()
            print(f"Répertoire introuvable : {racine}")
            continue

        print()
        print(f"Recherche dans : {racine}")
        print("Recherche des fichiers .uicue en cours...")

        dossiers = trouver_dossiers_shows(racine)

        if not dossiers:
            print()
            print("Aucun dossier contenant des fichiers .uicue n'a été trouvé.")
            print("Tu peux indiquer un autre répertoire de recherche.")
            continue

        print()
        print("DOSSIERS DE SHOW TROUVÉS")
        print("-" * 70)

        for numero, (dossier, nombre_fichiers) in enumerate(dossiers, start=1):
            try:
                chemin_affiche = dossier.relative_to(racine)
                if str(chemin_affiche) == ".":
                    chemin_affiche = Path(dossier.name)
            except ValueError:
                chemin_affiche = dossier

            print(f"{numero:02d} - {dossier.name} ({nombre_fichiers} fichiers .uicue)")
            print(f"     {chemin_affiche}")

        print()
        print("R - Rechercher dans un autre répertoire")
        print("Q - Quitter")

        while True:
            choix = input("Numéro du dossier à restaurer : ").strip()

            if choix.upper() == "Q":
                return None

            if choix.upper() == "R":
                break

            if not choix.isdigit():
                print("Saisie invalide : indique un numéro de la liste, R ou Q.")
                continue

            numero = int(choix)
            if not 1 <= numero <= len(dossiers):
                print(f"Numéro invalide : choisis un nombre entre 1 et {len(dossiers)}.")
                continue

            dossier_choisi, nombre_fichiers = dossiers[numero - 1]
            print()
            print(f"Dossier sélectionné : {dossier_choisi}")
            print(f"Show ciblé         : {dossier_choisi.name}")
            print(f"Fichiers .uicue     : {nombre_fichiers}")
            return dossier_choisi


# ============================================================
# MENU PRINCIPAL
# Choix de l'IP de la soundcraft
# Chemin du dossier du show, on peut mettre le ptyhon à la source
# du dossier pour éviter de taper le chemin
# V pour visualiser
# E pour exécuter
# Q pour quitter
# ============================================================

def main():

    global HOST, DEFAULT_HOST

    print()
    print("=" * 70)
    print("RESTORE CUES V10 - SOUNDCRAFT Ui24R (Windows / Linux)")
    print("=" * 70)

    # --------------------------------------------------------
    # SAISIE ET MÉMORISATION DE L'ADRESSE IP
    # --------------------------------------------------------

    HOST = demander_adresse_ip()

    if HOST != DEFAULT_HOST:

        if memoriser_adresse_ip(HOST):
            DEFAULT_HOST = HOST

    print()
    print(f"Adresse IP utilisée : {HOST}")
    print(f"Port                : {PORT}")

    # --------------------------------------------------------
    # CHOIX DU SHOW PAR NUMÉRO
    # --------------------------------------------------------

    dossier = choisir_dossier_show()

    if dossier is None:
        print()
        print("Sélection annulée. Fin du programme.")
        return

    # LE NOM DU DOSSIER EST LE NOM DU SHOW

    nom_show = dossier.name

    print()
    print(f"Dossier : {dossier}")
    print(f"Show    : {nom_show}")

    # RECHERCHE DES CUES

    cues = trouver_cues(dossier)
    afficher_liste_cues(cues, dossier)

    if not cues:
        return

    # --------------------------------------------------------
    # MENU
    # --------------------------------------------------------

    while True:

        print()
        print("=" * 70)
        print("MENU")
        print("=" * 70)

        print()
        print("V  - Visualiser les paramètres")
        print("E  - Exécuter la reconstruction")
        print("Q  - Quitter")
        print()

        choix = input("Votre choix : ").strip().upper()

        # VISUALISATION

        if choix == "V":

            visualiser_cues(cues)

        # RECONSTRUCTION AVEC SÉLECTION DES CUES

        elif choix == "E":

            # Réafficher la liste complète avec les numéros d'origine.
            afficher_liste_cues(cues, dossier)

            cues_selectionnes = selectionner_cues(cues)

            if cues_selectionnes:
                reconstruire_cues(cues_selectionnes, nom_show)
        # QUITTER

        elif choix == "Q":

            print()
            print("Fin du programme.")
            break

        else:

            print()
            print("Choix invalide.")


# ============================================================
# LANCEMENT
# ============================================================

if __name__ == "__main__":

    main()