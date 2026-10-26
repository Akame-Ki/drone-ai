#!/usr/bin/env bash
#
# Lance l'environnement de dev CoDrone EDU dans un conteneur Podman.
#
#   ./scripts/run.sh                          -> shell interactif
#   ./scripts/run.sh python examples/hello_drone.py
#   ./scripts/run.sh python -m codrone_edu request state 10 0.2
#
# Variables :
#   IMAGE=codrone-dev:3.12   nom/tag de l'image
#   FORCE_BUILD=1            reconstruit l'image avant de lancer
#
set -euo pipefail

IMAGE="${IMAGE:-codrone-dev:3.12}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Build automatique -------------------------------------------------------
if [[ "${FORCE_BUILD:-0}" == "1" ]] || ! podman image exists "$IMAGE"; then
    echo ">> Construction de l'image $IMAGE..."
    podman build -t "$IMAGE" "$REPO_ROOT"
fi

# --- Détection du contrôleur CoDrone EDU ------------------------------------
# La librairie utilise pyserial et repère le contrôleur par son VID USB :
#   0x0483 = STMicroelectronics (CDC-ACM, /dev/ttyACM*)
#   0x1a86 = QinHeng CH340     (/dev/ttyUSB*)
vid_of() {
    local tty="$1" dir
    dir="$(readlink -f "/sys/class/tty/$tty/device" 2>/dev/null || true)"
    while [[ -n "$dir" && "$dir" != "/" ]]; do
        if [[ -f "$dir/idVendor" ]]; then
            cat "$dir/idVendor"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    return 1
}

controllers=()
for sys_tty in /sys/class/tty/ttyACM* /sys/class/tty/ttyUSB*; do
    [[ -e "$sys_tty" ]] || continue
    tty="$(basename "$sys_tty")"
    vid="$(vid_of "$tty" || true)"
    case "${vid,,}" in
        0483 | 1a86) controllers+=("/dev/$tty") ;;
    esac
done

if (( ${#controllers[@]} > 0 )); then
    echo ">> Contrôleur CoDrone EDU détecté : ${controllers[*]}"
else
    echo ">> Aucun contrôleur CoDrone EDU détecté pour l'instant."
    echo "   Branche la manette avec le câble USB fourni (câble data),"
    echo "   puis vérifie avec : make ports"
fi

# --- Lancement ---------------------------------------------------------------
# Notes rootless / Fedora :
#   * -v /dev:/dev      : --device-cgroup-rule n'est pas supporté en rootless.
#                         Le montage de /dev permet aussi le hot-plug.
#   * label=disable     : SELinux est Enforcing sur l'hôte.
#   * keep-groups       : conserve le groupe dialout dans le conteneur.
podman_args=(--rm -i)
if [[ -t 0 && -t 1 ]]; then
    podman_args+=(-t)
fi

if (( $# == 0 )); then
    set -- bash
fi

exec podman run "${podman_args[@]}" \
    --security-opt label=disable \
    --group-add keep-groups \
    -v /dev:/dev \
    -v "$REPO_ROOT":/workspace \
    -w /workspace \
    -e TERM="${TERM:-xterm-256color}" \
    -e COLORTERM="${COLORTERM:-truecolor}" \
    "$IMAGE" "$@"
