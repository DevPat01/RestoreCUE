# Tests et validations de RestoreCUE

## 1. Environnement et portée des essais

Les essais rapportés ont été réalisés avec une console Soundcraft Ui24R réelle, connectée à un ordinateur. Le logiciel a également été utilisé sous Windows et Linux Mint.

Les fichiers `.uicue` utilisés lors des essais contenaient 2 356 commandes par Cue.

Les paramètres de délai utilisés lors des essais les plus récents étaient :

```python
DELAY_BETWEEN_PARAMS = 0.001
DELAY_AFTER_CUE = 0.3
```

Les résultats ci-dessous sont des essais effectués sur la configuration décrite. Ils ne constituent pas une certification de compatibilité avec toutes les versions de firmware, toutes les configurations réseau ou tous les Shows.  

Tous les essais de validation de RestoreCUE ont été réalisés avec une connexion Ethernet filaire (RJ45) entre l'ordinateur et la console Soundcraft Ui24R.

Les temps d'exécution relevés correspondent exclusivement à cette configuration. Aucune mesure comparative ni validation des performances en Wi-Fi n'a été effectuée.

## 2. Vérification préalable du Show — `SHOWLIST`

Un essai a été effectué avec un Show cible nommé `TestPat` qui ne figurait pas dans la liste de la console.

Résultat observé :

-   le programme a reçu la liste des Shows ;
-   `TestPat` a été indiqué comme absent ;
-   la restauration a été interrompue ;
-   aucun `SETD` ni `SAVECUE` n'a été envoyé ;
-   les threads ont été arrêtés et le socket a été fermé proprement.

Un autre essai a confirmé la présence de `TestPat` dans `SHOWLIST` et a permis de poursuivre la restauration.

## 3. Restaurations réalisées et résultats obtenus

| Essai | Cues sélectionnés | Cues retrouvés | Cues manquants | Temps estimé | Temps réel |
| --- | --: | --: | --: | --: | --: |
| Restauration d'un Cue | 1 | 1 | 0 | 4 s | 5 s |
| Restauration de deux Cues | 2 | 2 | 0 | 7 s | 9 s |
| Restauration partielle | 10 | 10 | 0 | 44 s | 46 s |
| Restauration complète — essai 1 | 41 | 41 | 0 | 2 min 17 s | 3 min 01 s |
| Restauration complète — essai 2 | 41 | 41 | 0 | 3 min 00 s | 3 min 08 s |

### Restauration d'un Cue

Un Cue nommé `CUE2` a été reconstruit à partir de 2 356 commandes. Le contrôle final a retrouvé le Cue dans la liste du Show.

### Restauration partielle de 10 Cues

Dix Cues ont été sélectionnés dans un Show qui en contenait 41. Le contrôle final a retrouvé les dix Cues attendus ; la liste totale du Show contenait toujours 41 Cues.

### Restauration complète de 41 Cues

Deux restaurations complètes ont été rapportées. Dans les deux cas, les 41 Cues attendus ont été retrouvés et aucun Cue manquant n'a été signalé.

## 4. Vérification finale — `CUELIST`

La réponse `CUELIST` a permis de comparer les noms des Cues sélectionnés avec ceux renvoyés par la console.

Les résultats rapportés sont :

-   1 Cue attendu : 1 retrouvé ;
-   2 Cues attendus : 2 retrouvés ;
-   10 Cues attendus : 10 retrouvés ;
-   41 Cues attendus : 41 retrouvés lors de deux essais.

Dans les essais partiels, le nombre total de Cues renvoyé par la console était supérieur ou égal au nombre de Cues sélectionnés, ce qui est normal lorsque le Show contient déjà d'autres Cues.

**Limite :** la réponse `CUELIST` confirme la présence des noms. Elle ne permet pas, à elle seule, de contrôler les 2 356 valeurs de paramètres de chaque Cue.

## 5. Arrêt des threads et fermeture du socket

Après la mise en place d'un arrêt coopératif :

-   le thread d'observation a indiqué que l'arrêt était demandé et que la lecture était terminée ;
-   les threads d'observation et `ALIVE` ont été arrêtés avant la fermeture du socket ;
-   le programme a affiché la fermeture propre du socket ;
-   aucun nouveau message `WinError 10053` n'a été rapporté dans les essais réussis présentés ici.

Les temps d'arrêt mesurés dans les essais indiqués étaient de l'ordre de 0,01 à 0,04 seconde.

## 6. Observations sur les durées

Les temps estimés ont été ajustés au fil des essais. Sur les petites restaurations, l'écart entre estimation et durée réelle a été de quelques secondes. Sur les restaurations de 41 Cues, le second essai a donné une estimation de 3 minutes pour une durée réelle de 3 minutes et 8 secondes.

Ces mesures restent indicatives. Il est préférable de conserver une marge dans l'estimation plutôt que de considérer les durées observées comme garanties.

## 7. Ce qui reste à vérifier

Les essais décrits confirment les points suivants :

-   la connexion à la console et la réception des réponses de listes ;
-   le contrôle préalable de présence du Show ;
-   l'envoi des commandes et l'enregistrement des Cues ;
-   la présence des noms attendus dans `CUELIST` après restauration ;
-   l'arrêt propre des threads et la fermeture du socket.

Ils ne démontrent pas à eux seuls que chaque valeur de chacun des paramètres a été enregistrée sans erreur. Pour une validation complète du contenu, il reste recommandé de rappeler des Cues sur la console et de contrôler leurs réglages, ou de comparer une lecture détaillée de leur état lorsque cette méthode est disponible.