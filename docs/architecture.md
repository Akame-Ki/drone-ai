# Architecture

## Comment le code parle au drone

```
PC (script Python) ──USB──> manette ──radio──> drone
```

Le firmware du drone est fermé : **aucun code n'est envoyé sur le drone**. Le
script tourne sur le PC et envoie des commandes en direct. Si le script s'arrête
ou si le câble se débranche, le drone ne reçoit plus d'ordres.

**Un seul programme à la fois** peut ouvrir le port série (`COM5`, `/dev/ttyACM0`).
C'est pour ça que le contrôle et le HUD sont dans la même fenêtre.

## Fichiers

| Fichier | Rôle |
|---|---|
| `src/codrone_project/telemetry.py` | thread qui demande tous les flux de données au drone, garde 30 s d'historique |
| `scripts/hud.py` | fenêtre tkinter : vue basique + vue avancée (graphes), lecture seule |
| `scripts/control.py` | pilotage clavier (`Pilot`) + fenêtre (`ControlHud`, hérite de `Hud`) |
| `scripts/tactical.py` | vue tactique : FPV synthétique, lidar, trajectoire 3D |

Les scripts ajoutent `src/` au `sys.path`, rien à installer en plus de
`requirements.txt` (tkinter est fourni avec Python sous Windows).

## Télémétrie (`Telemetry`)

- La librairie range chaque paquet reçu dans des listes de l'objet `Drone`
  (`state_data`, `motion_data`, …). `Telemetry` envoie des requêtes (`sendRequest`)
  selon trois rythmes (voir [hud.md](hud.md)) puis recopie ces listes dans un seul
  dictionnaire `values`.
- `snapshot()` renvoie une copie de `values` + de l'historique, utilisable depuis le
  thread de l'interface.
- `linked()` est vrai si un paquet `State` est arrivé il y a moins de 2 s.

## Pilotage (`Pilot`)

- Un thread à 20 Hz transforme les touches tenues en `(roll, pitch, yaw, throttle)`
  et appelle `sendControl`, **seulement** si l'état de vol est `TakeOff` ou `Flight`.
- Décollage / atterrissage : `sendTakeOff` / `sendLanding` réessayés pendant 2 s
  jusqu'au changement d'état. Les fonctions `takeoff()` / `land()` de la librairie ne
  sont pas utilisées : elles bloquent ~4 s et renverraient la commande après un
  arrêt d'urgence.
- **Verrou série** : la librairie n'a pas de verrou, et la télémétrie et le pilotage
  écrivent depuis deux threads. `lock_serial_writes()` entoure `drone.transfer` d'un
  `threading.Lock` pour que les paquets ne se mélangent pas.

## Interface

- `Hud.refresh()` redessine tout le canvas toutes les 100 ms, puis appelle
  `draw_overlay()` (vide dans `Hud`, utilisé par `ControlHud`).
- `ControlHud` ajoute les touches, le cycle de vues (`VIEWS`) et délègue la vue
  tactique à `TacticalView.draw()`.
- La répétition automatique des touches est filtrée : un relâchement n'est pris en
  compte qu'après 40 ms sans nouvel appui.

## Ajouter…

**Une touche** : dans `ControlHud.on_press`, ajoute une branche (après `elif not first`
si elle ne doit se déclencher qu'une fois par appui), et une méthode dans `Pilot` qui
appelle la librairie et `self.say("...")` pour le message et le journal.

**Une donnée** : ajoute le `DataType` dans `FAST` / `MEDIUM` / `SLOW`
(`telemetry.py`), lis la liste correspondante dans `_update()`, et ajoute la clé à
`HISTORY_KEYS` pour pouvoir la tracer. Pour un nouveau graphe, une ligne dans
`CHARTS` (`hud.py`).

## Référence

Toutes les commandes de la librairie `codrone_edu` : [commands.md](commands.md).
