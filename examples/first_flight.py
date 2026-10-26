"""Premier vol : décollage, hover 3 s, atterrissage.

À lancer dans un espace dégagé, drone posé au sol, batterie chargée.

Usage :
    make run FILE=examples/first_flight.py
"""

import time

from codrone_edu.drone import Drone

MIN_BATTERY_PERCENT = 30


def main() -> None:
    drone = Drone()
    try:
        print("Connexion au contrôleur CoDrone EDU...")
        drone.connect()

        battery = drone.get_battery()
        print(f"Batterie : {battery}%")
        if battery < MIN_BATTERY_PERCENT:
            raise SystemExit(
                f"Batterie trop faible (< {MIN_BATTERY_PERCENT}%), vol annulé."
            )

        print("Décollage dans 3 secondes...")
        time.sleep(3)
        drone.takeoff()

        print("Hover 3 secondes...")
        drone.hover(3)

        print("Atterrissage...")
        drone.land()
        print("Vol terminé.")
    finally:
        drone.close()


if __name__ == "__main__":
    main()
