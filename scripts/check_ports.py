#!/usr/bin/env python3
"""Diagnostic des ports série vus depuis le conteneur.

Usage :
    ./scripts/run.sh python scripts/check_ports.py
    ./scripts/run.sh python scripts/check_ports.py --all   # inclut ttyS*
    make ports
"""

from __future__ import annotations

import argparse
import sys

from serial.tools import list_ports

# VID des contrôleurs CoDrone EDU reconnus par la librairie codrone-edu.
KNOWN_VIDS = {
    0x0483: "STMicroelectronics (contrôleur CoDrone EDU, CDC-ACM)",
    0x1A86: "QinHeng CH340 (contrôleur CoDrone EDU, USB-série)",
}


def describe(port) -> str:
    if port.vid is not None and port.pid is not None:
        ids = f"{port.vid:04x}:{port.pid:04x}"
    else:
        ids = "----:----"
    return f"  {port.device:<16} {ids}  {port.description or 'n/a'}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Liste les ports série et détecte un CoDrone EDU.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="afficher aussi les ports sans identifiant USB (ttyS*, consoles...)",
    )
    args = parser.parse_args()

    all_ports = sorted(list_ports.comports(), key=lambda p: p.device)
    usb_ports = [p for p in all_ports if p.vid is not None]
    ports = all_ports if args.all else usb_ports

    if not ports:
        print("Aucun port série USB détecté.")
        if all_ports:
            print(f"({len(all_ports)} port(s) non-USB masqué(s), relance avec --all pour les voir.)")
        print()
        print("Vérifie que :")
        print("  - la manette est branchée avec un câble USB *data* ;")
        print("  - le périphérique apparaît sur l'hôte : ls /dev/ttyACM* /dev/ttyUSB* ;")
        print("  - le conteneur est lancé avec -v /dev:/dev (c'est le cas via run.sh).")
        return 1

    print(f"{len(ports)} port(s) série affiché(s) :\n")
    found = False
    for port in ports:
        label = KNOWN_VIDS.get(port.vid)
        print(describe(port) + ("  ==> CoDrone EDU" if label else ""))
        if label:
            found = True
            print(f"  {'':<16} {label}")
        if port.hwid and port.hwid != "n/a":
            print(f"  {'':<16} hwid={port.hwid}")
        print()

    if found:
        print("Contrôleur CoDrone EDU prêt à l'emploi.")
        return 0

    print("Aucun contrôleur CoDrone EDU reconnu.")
    print("VID attendus : 0483 (STM32) ou 1a86 (CH340).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
