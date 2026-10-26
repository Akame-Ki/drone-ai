# drone-ai — environnement CoDrone EDU (Podman + Python 3.12)

Environnement de développement reproductible pour programmer un drone **CoDrone EDU**
avec la librairie Python [`codrone-edu`](https://pypi.org/project/codrone-edu/).

- Image : `python:3.12-slim` + `codrone-edu==2.10` (numpy, Pillow, pyserial, colorama).
- Podman **rootless**, SELinux géré, accès série USB et hot-plug.
- Deux modes de lancement : `scripts/run.sh` (quotidien) ou `compose.yaml`.

## Contenu

```
Containerfile                  image de dev Python 3.12
requirements.txt               codrone-edu==2.10
compose.yaml                   service Podman Compose
scripts/run.sh                 lanceur + détection du contrôleur
scripts/check_ports.py         diagnostic des ports série
examples/hello_drone.py        test sans vol (batterie + LED)
examples/first_flight.py       décollage / hover / atterrissage
udev/99-codrone-edu.rules      accès série pour l'utilisateur connecté
.devcontainer/devcontainer.json config VS Code Dev Containers
Makefile                       raccourcis
```

## Prérequis

- Podman ≥ 5 (testé avec 5.8.9), Fedora 44.
- Un drone **CoDrone EDU** et la manette, reliée au PC par le **câble USB fourni**
  (câble *data*, pas un câble de charge seule).
- Sur Linux, le drone se connecte via la manette ; le contrôleur apparaît comme
  `/dev/ttyACM*` (VID `0x0483`, STM32) ou `/dev/ttyUSB*` (VID `0x1a86`, CH340).

### Accès au port série (une seule fois)

**Option recommandée — règle udev avec ACL** (pas besoin de toucher aux groupes) :

```bash
sudo install -m 644 udev/99-codrone-edu.rules /etc/udev/rules.d/
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=tty
# puis débranche / rebranche la manette
```

**Alternative — groupe `dialout`** :

```bash
sudo usermod -aG dialout "$USER"
# déconnexion/reconnexion (ou `newgrp dialout`) pour prendre effet
```

Vérifie ensuite côté hôte :

```bash
lsusb | grep -Ei '0483|1a86'      # contrôleur visible ?
ls -l /dev/ttyACM* /dev/ttyUSB*   # permissions / ACL
```

## Démarrage rapide

```bash
make build      # construit l'image codrone-dev:3.12
make shell      # shell bash dans le conteneur, repo monté dans /workspace

# dans le conteneur :
python scripts/check_ports.py
python examples/hello_drone.py
```

Ou en une commande depuis l'hôte :

```bash
./scripts/run.sh python scripts/check_ports.py
./scripts/run.sh python examples/hello_drone.py
./scripts/run.sh python examples/first_flight.py   # ⚠️ le drone décolle
```

`scripts/run.sh` construit l'image automatiquement si elle n'existe pas et affiche
le port du contrôleur détecté. Sans argument, il ouvre un shell.

## Raccourcis Make

| Commande | Effet |
|---|---|
| `make build` / `make rebuild` | construit / reconstruit l'image |
| `make shell` | shell interactif |
| `make run FILE=examples/first_flight.py` | exécute un script (défaut : `hello_drone.py`) |
| `make ports` | liste les ports série et détecte le contrôleur |
| `make telemetry` | télémétrie brute : `python -m codrone_edu request state 10 0.2` |
| `make compose-up` / `compose-down` / `compose-shell` | via `podman compose` |
| `make clean` | supprime l'image locale |

## Podman Compose

Le provider compose de Podman (docker-compose) passe par le socket Podman :

```bash
systemctl --user enable --now podman.socket
podman compose up -d
podman compose exec codrone bash
podman compose down
```

Si le provider docker-compose pose problème, utilise `run.sh` (même configuration)
ou installe `podman-compose`.

## VS Code Dev Containers

Prérequis : extension **Dev Containers** (`ms-vscode-remote.remote-containers`).

L'extension doit piloter **Podman** et non Docker. Ajoute ce réglage dans les
paramètres **utilisateur** de VS Code (`Ctrl+,` → chercher `dev.containers.dockerPath`) :

```json
"dev.containers.dockerPath": "podman"
```

Puis :

1. ouvrir le dossier `drone-ai` dans VS Code ;
2. `F1` → **Dev Containers: Reopen in Container** ;
3. le terminal intégré s'ouvre dans `/workspace` avec Python 3.12 ;
4. vérifier avec `python scripts/check_ports.py` ;
5. après une modification du `Containerfile` ou de `requirements.txt` :
   `F1` → **Dev Containers: Rebuild Container**.

Le conteneur monte `/dev` : le hot-plug de la manette fonctionne sans rouvrir
la fenêtre. Les fichiers créés restent possédés par ton utilisateur hôte.

> Dans le terminal VS Code, **ne lance pas `make shell`** : Podman n'existe pas
> à l'intérieur du conteneur. Lance directement `python ...` ou `make run`.


## Dépannage

**`Permission denied: '/dev/ttyACM0'`**
- La règle udev n'est pas active : réinstalle-la, `udevadm trigger`, rebranche.
- Ou l'utilisateur n'est pas dans `dialout` et n'a pas reconnecté sa session.
- Vérifie dans le conteneur : `ls -l /dev/ttyACM0` puis
  `python -c "import os; os.open('/dev/ttyACM0', os.O_RDWR)"`.

**Aucun port détecté**
- Câble USB de charge seule → utilise le câble fourni.
- Manette non allumée / drone non appairé : allume la manette, attends l'état LINK.
- `make ports` ne voit rien alors que `ls /dev/ttyACM*` fonctionne sur l'hôte :
  le conteneur a été lancé sans `-v /dev:/dev` (utilise `run.sh`).

**Hot-plug**
- Le conteneur monte `/dev`, donc un drone branché après le démarrage est visible.
- Si tu utilises `podman run` à la main avec `--device`, il faut relancer le conteneur
  après chaque branchement.

**SELinux (Fedora)**
- `run.sh` et `compose.yaml` utilisent `--security-opt label=disable` pour le bind
  mount du repo. Ne retire pas cette option sans adapter les labels (`:z`).

**VS Code ouvre le conteneur avec Docker**
- Vérifie le réglage utilisateur `"dev.containers.dockerPath": "podman"`.
- Sinon `F1` → **Dev Containers: Rebuild Without Cache** après l'avoir ajouté.


**Mise à jour du firmware**
- `./scripts/run.sh python -m codrone_edu update` (l'accès réseau sortant
  fonctionne par défaut avec le réseau Podman).
- Ne débranche pas pendant la mise à jour.

## Notes techniques

- **Python 3.12** : la doc Robolink recommande 3.11 à cause d'un souci de
  *virtualenv* sous 3.12 (note de 2023). Ce conteneur n'utilise pas de virtualenv :
  l'installation système fonctionne, et la combinaison
  `codrone-edu 2.10 + numpy 2.5.4 + Pillow 13` a été validée en 3.12 comme en 3.14.
- **Rootless** : `--device-cgroup-rule` n'est pas supporté ; on monte `/dev`
  directement, ce qui couvre aussi le hot-plug. Aucun `--privileged`.
- **Image minimale** : pas de matplotlib/pandas/Jupyter. Pour les ajouter, crée un
  `requirements-dev.txt` et une étape `pip install` dans le `Containerfile`.
- Les fichiers créés dans `/workspace` restent possédés par ton utilisateur hôte
  (root du conteneur = ton uid en rootless).
