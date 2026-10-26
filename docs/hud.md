# HUD de télémétrie — `scripts/hud.py`

Affiche en direct tout ce que le drone envoie. **Lecture seule** : n'envoie aucune
commande de vol, on peut le laisser ouvert sans risque.

```bash
python scripts/hud.py                 # détection auto du port
python scripts/hud.py COM5            # Windows (Linux : /dev/ttyACM0)
python scripts/hud.py COM5 --advanced # démarre en vue avancée
```

Tab bascule entre la vue basique et la vue avancée. Pour piloter en voyant le HUD,
utilise [`control.py`](controle.md), qui l'inclut.

> Lance-le sur l'hôte (fenêtre tkinter). Sous Linux, installe tkinter si besoin :
> `sudo dnf install python3-tkinter`.

## Vue basique

Horizon artificiel (roulis / tangage), batterie, état de vol / mouvement / système,
cap, hauteur, distance frontale, position, niveau de vitesse, headless.
Alerte **OBSTACLE** sous 50 cm. `NO DATA` si aucun paquet depuis 2 s.

## Vue avancée

**Graphes (30 dernières secondes)**

| Graphe | Unité | Source |
|---|---|---|
| Attitude (roll, pitch) | ° | Motion |
| Heading (yaw) | ° | Motion |
| Gyro rate | °/s | Motion |
| Accel x/y/z | brut | Motion |
| Height : ToF, alt ToF, pos z | cm | Range, Altitude, Position |
| Front range | cm (max 150) | Range |
| Position x/y | m | Position |
| Optical flow x/y | m | RawFlow |
| Battery | % | State |
| Pressure | Pa | Altitude |
| Temperature | °C | Altitude |
| Path (vue de dessus) | m | Position + cap |

**Panneau latéral**

- **STATE** : vol, mouvement, système, mode de contrôle, headless, niveau de vitesse, orientation
- **SENSORS** : distances avant/bas, température, altitude barométrique, accéléro et gyro bruts
- **COLOR SENSORS** : couleur détectée avant/arrière + HSVL + pastille de couleur, carte
- **CONTROLLER** : joysticks gauche/droit, boutons
- **TRIM** : roll / pitch / yaw / throttle
- **FLAGS** : flags d'erreur décodés (vert = état de liaison `RF_*`, rouge = problème)
- **LIFETIME** : temps de vol, décollages / atterrissages, accidents
- **FIRMWARE** : modèle et version du drone et de la manette

## Fréquences de rafraîchissement

| Flux | Fréquence |
|---|---|
| State, Motion, Range, Position, Altitude, RawFlow | ~6 Hz |
| CardColor, RawMotion, Joystick, Error | ~1 Hz |
| Trim, Count, Information (drone + manette) | toutes les ~6 s |

## Flags d'erreur courants

| Flag | Signification |
|---|---|
| `Motion_Calibrating` / `Motion_NotCalibrated` | IMU en calibration : pose le drone à plat, immobile |
| `Flow_CannotRecognizeGroundImage` | sol trop uni ou trop sombre pour l'optical flow |
| `LowBattery` | batterie faible |
| `Attitude_NotStable` | drone trop incliné ou retourné |
| `TakeoffFailure_CheckPropellerAndMotor` | décollage raté : vérifie hélices et moteurs |
| `CanNotFlip_LowBattery` | batterie trop faible pour un flip |

## À vérifier

Unités confirmées par le code de la librairie, sauf : l'échelle de l'accéléromètre,
l'unité du temps de vol (LIFETIME) et le format des boutons, affichés tels quels.
