# 1. Image de base : Python 3.12 version légère (slim)
FROM python:3.12-slim

# 2. Variables d'environnement pour Python
# Evite la création de fichiers .pyc
ENV PYTHONDONTWRITEBYTECODE=1

# Force les logs à sortir directement dans la console (pas de buffer)
ENV PYTHONUNBUFFERED=1

# 3. Création du dossier de travail dans le conteneur
WORKDIR /app

# 4. Installation des dépendances système (optionnel, mais souvent utile pour gcc, aws, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 5. Copie du fichier requirements et installation des libs Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copie de tout le reste du code source
COPY . .

# 7. Création des dossiers nécessaires (logs, data)
RUN mkdir -p logs data/downloaded

# 8. Commande par défaut au lancement du conteneur
# On lance le pipeline principal
CMD ["python", "-m", "src.main"]