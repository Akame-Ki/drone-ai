IMAGE ?= codrone-dev:3.12
FILE  ?= examples/hello_drone.py

.PHONY: help build rebuild shell run ports telemetry compose-up compose-down compose-shell clean

help:
	@echo "Cibles disponibles :"
	@echo "  make build          Construit l'image $(IMAGE)"
	@echo "  make rebuild        Reconstruit l'image sans cache"
	@echo "  make shell          Shell interactif dans le conteneur"
	@echo "  make run FILE=...   Exécute un script Python (défaut : $(FILE))"
	@echo "  make ports          Liste les ports série et détecte le contrôleur"
	@echo "  make telemetry      Affiche la télémétrie (10 échantillons, 0.2 s)"
	@echo "  make compose-up     Démarre le service via podman compose"
	@echo "  make compose-down   Arrête le service compose"
	@echo "  make compose-shell  Shell dans le service compose"
	@echo "  make clean          Supprime l'image locale"

build:
	podman build -t $(IMAGE) .

rebuild:
	podman build --no-cache -t $(IMAGE) .

shell:
	./scripts/run.sh

run:
	./scripts/run.sh python $(FILE)

ports:
	./scripts/run.sh python scripts/check_ports.py

telemetry:
	./scripts/run.sh python -m codrone_edu request state 10 0.2

compose-up:
	podman compose up -d

compose-down:
	podman compose down

compose-shell:
	podman compose exec codrone bash

clean:
	podman rmi -f $(IMAGE) 2>/dev/null || true
