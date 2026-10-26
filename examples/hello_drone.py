"""Smoke test sans vol : connexion, batterie et LED.

Usage :
    make run FILE=examples/hello_drone.py
    ./scripts/run.sh python examples/hello_drone.py
"""

import time

from codrone_edu.drone import Drone


def main() -> None:
    drone = Drone()
    try:
        print("Connexion au contrôleur CoDrone EDU...")
        drone.connect()

        battery = drone.get_battery()
        print(f"Batterie : {battery}%")
        if battery < 30:
            print("Attention : batterie faible, pense à recharger avant de voler.")

        print("LED verte pendant 2 secondes.")
        drone.set_drone_LED(0, 255, 0, 100)
        time.sleep(2)
        drone.set_drone_LED(0, 0, 0, 0)

        print("OK : le drone répond.")
    finally:
        drone.close()


if __name__ == "__main__":
    main()
