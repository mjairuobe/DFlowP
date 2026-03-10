# DFlowP

**Framework für datenflussorientierte Programmierung**

DFlowP ist ein Python-Framework zur Entwicklung datenflussorientierter Anwendungen. Es bietet eine Event-basierte Architektur, MongoDB-Integration und einen modularen Aufbau mit Core-, Infrastructure- und Utils-Layer.

## Voraussetzungen

- Python 3.10+
- MongoDB (für Datenbankfunktionalität)

## Installation

### Mit pip

```bash
pip install -e .
```

### Mit dem Install-Skript (Ubuntu)

```bash
./install.sh
# Optional mit MongoDB: ./install.sh --with-mongodb
```

### Manuell

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

## Projektstruktur

- **dflowp/core** – Events, Engine, Processes
- **dflowp/infrastructure** – Datenbankrepositories (MongoDB)
- **dflowp/utils** – Logger und Hilfsfunktionen

## Tests

```bash
pytest tests/ -v
```

Hinweis: Für Datenbank-Tests muss MongoDB laufen (localhost:27017).

## Lizenz

Siehe [LICENSE](LICENSE) falls vorhanden.
