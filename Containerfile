# Environnement de développement CoDrone EDU
# Python 3.12 (voir README : la mise en garde Robolink sur 3.12 concerne virtualenv,
# pas la librairie ni l'usage dans ce conteneur).
ARG PYTHON_VERSION=3.12
FROM docker.io/library/python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace

# Outils nécessaires au confort de dev / VS Code (git, SSH, curl).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        openssh-client \
        curl \
        less \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

# Le code du projet est monté dans /workspace au lancement (scripts/run.sh
# ou compose.yaml). Par défaut on ouvre un shell.
CMD ["bash"]
