#!/bin/bash
# DFlowP - Installation auf Ubuntu
# Installiert Python-Abhängigkeiten und optional MongoDB

set -e

echo "=== DFlowP Installer für Ubuntu ==="

# Prüfen ob Python 3.10+ vorhanden
if ! command -v python3 &> /dev/null; then
    echo "Python3 nicht gefunden. Installiere Python..."
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv
fi

PYTHON_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python-Version: $PYTHON_VER"

# Virtuelle Umgebung erstellen (falls nicht vorhanden)
if [ ! -d "venv" ]; then
    echo "Erstelle virtuelle Umgebung..."
    python3 -m venv venv
fi

echo "Aktiviere virtuelle Umgebung..."
source venv/bin/activate

# pip aktualisieren
pip install --upgrade pip

# Python-Abhängigkeiten installieren
echo "Installiere Python-Abhängigkeiten..."
pip install -r requirements.txt

# Optional: MongoDB installieren (wenn --with-mongodb übergeben)
if [ "$1" = "--with-mongodb" ]; then
    echo "=== Optional: MongoDB installieren ==="
    if ! command -v mongod &> /dev/null; then
        echo "Installiere MongoDB..."
        curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
        echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
        sudo apt-get update
        sudo apt-get install -y mongodb-org
        sudo systemctl start mongod
        sudo systemctl enable mongod
        echo "MongoDB installiert und gestartet."
    else
        echo "MongoDB ist bereits installiert."
    fi
fi

echo ""
echo "=== Installation abgeschlossen ==="
echo "Aktivierung: source venv/bin/activate"
echo "Tests:       pytest tests/ -v"
echo ""
echo "Hinweis: Für Datenbank-Tests muss MongoDB laufen (localhost:27017)."
echo "         MONGODB_URI und MONGODB_TEST_DB können gesetzt werden."
echo ""
