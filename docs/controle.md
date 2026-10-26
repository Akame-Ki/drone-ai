# Contrôle clavier — `scripts/control.py`

Pilote le drone au clavier, avec le HUD à l'écran.

```bash
python scripts/control.py COM5               # Windows (Linux : /dev/ttyACM0)
python scripts/control.py COM5 --power 25    # puissance des sticks 1-100 (défaut 40)
python scripts/control.py COM5 --advanced    # démarre directement en vue tactique
```

Sans port, la librairie le détecte toute seule. **Ferme `hud.py` avant** : un seul
programme peut ouvrir le port série (le HUD est déjà inclus dans `control.py`).

> Lance-le sur l'hôte, pas dans le conteneur : c'est une fenêtre tkinter, et le
> conteneur n'a pas d'affichage graphique.

## Touches

La fenêtre doit avoir le focus.

| Touche | Action |
|---|---|
| W / S | avancer / reculer |
| A / D | gauche / droite |
| Q / E | tourner à gauche / à droite |
| Shift / Ctrl | monter / descendre |
| Espace | décollage / atterrissage |
| **Échap** | **ARRÊT D'URGENCE : moteurs coupés, le drone tombe** |
| Tab | vue : basique → tactique → graphes |
| + / - / molette | puissance des sticks ±10 (10–100) |
| F1 / F2 / F3 | niveau de vitesse du drone 1–3 (réglage firmware, 3 = très rapide) |
| Flèches | flip avant / arrière / gauche / droite |
| H | mode headless on/off (l'« avant » reste le même même si le drone tourne) |
| R | retour au point de décollage |
| L | change la couleur des LED |
| C | efface la carte lidar et la trajectoire 3D |
| Clic-glisser | fait tourner la vue 3D (vue tactique) |

Les touches suivent les noms des lettres (`keysym`), pas leur position : sur un
clavier AZERTY, W/A/Q ne sont pas à la place habituelle.

## Comportement et sécurité

- **Aucune touche = vol stationnaire.** Les commandes de sticks sont envoyées à
  20 Hz, uniquement quand le drone est en `TakeOff` ou `Flight` : appuyer sur W au
  sol ne fait rien.
- **Espace** décolle si le drone est `Ready`, atterrit s'il est en vol. Rester
  appuyé ne déclenche pas deux fois.
- **Perte du focus** (clic sur une autre fenêtre) : toutes les touches sont
  relâchées, le drone reste en stationnaire.
- **Fermer la fenêtre en vol** : le drone atterrit d'abord, puis le programme s'arrête.
- **Échap** coupe les moteurs immédiatement, même pendant un décollage. À garder
  pour les vraies urgences : le drone tombe.
- **Flips** : seulement en vol, batterie ≥ 50 %, et 4 s minimum entre deux flips.
  Sinon un message explique le refus (« flip refused: battery 42 % »).
- **Retour maison (R)** : seulement en vol.
- Chaque action affiche un message pendant 3 s et s'ajoute au journal d'événements.

### Premiers vols

1. `--power 25`, grande pièce dégagée.
2. Sol éclairé et texturé (le capteur optical flow en a besoin pour tenir la position).
3. Batterie > 50 %, garde un doigt près d'Échap.
4. Vérifie le sens de chaque axe à basse puissance (voir « À vérifier »).

## Les vues

**Basique** : horizon artificiel, batterie, état de vol, distances, position, et
en bas un clavier qui s'allume selon les touches tenues, la barre de puissance et
les messages.

**Tactique** (style cockpit, vert phosphore) :

- **FPV synthétique** : le CoDrone EDU n'a pas de caméra, cette vue est dessinée
  à partir des capteurs. Échelle de tangage (pointillés sous l'horizon), échelle de
  roulis, bandeau de cap, bandeaux hauteur (cm) et vitesse sol (cm/s) avec vitesse
  verticale, réticule. Alertes clignotantes : obstacle < 50 cm, batterie faible,
  défauts capteurs, perte de liaison, arrêt d'urgence.
- **Lidar** : le drone n'a qu'un capteur de distance frontal. Chaque mesure est
  placée sur une carte selon la position et le cap du drone, donc **tourner sur
  place (Q/E) balaie la pièce** et dessine les murs. Vue « cap en haut », anneaux
  tous les 0,5 m, points qui s'estompent en 90 s, cône du capteur en orange quand
  il touche quelque chose.
- **Trajectoire 3D** : tout le vol en perspective, grille au sol, pad de décollage
  (H), lignes verticales vers le sol, flèche de cap, points lidar en 3D, distance
  totale. Tourne toute seule ; clic-glisser pour la bouger (reprend 5 s après).
- **Console** : état, clavier, position des deux sticks, puissance, journal horodaté.

**Graphes** : la vue avancée du HUD, voir [hud.md](hud.md).

La trajectoire et le lidar sont enregistrés quelle que soit la vue affichée.

## À vérifier sur le vrai drone

Le code a été testé avec un drone simulé. Hypothèses tirées de la doc de la
librairie, à confirmer en vol :

- position : x = avant, y = gauche, z = haut (m) ; le cap augmente en tournant à gauche ;
- sens de chaque touche (si A part à droite ou Q tourne du mauvais côté, c'est un
  signe à inverser dans `Pilot._loop`) ;
- si la carte lidar est en miroir ou « bave » quand le drone tourne, c'est le même
  type de signe dans `TacticalView.ingest` ;
- distance réelle parcourue par le retour maison, effet réel du niveau de vitesse 3.

## Dépannage

| Problème | Solution |
|---|---|
| `NO LINK` / `SIGNAL LOST` | drone éteint ou pas appairé à la manette ; vérifie aussi que `hud.py` n'est pas ouvert |
| Les touches ne font rien | clique dans la fenêtre (focus) ; le drone doit être en vol |
| Espace ne décolle pas | le drone doit être `Ready` (pas en erreur, pas de flag rouge) |
| Flip refusé | lis le message : batterie, pas en vol, ou attente entre deux flips |
