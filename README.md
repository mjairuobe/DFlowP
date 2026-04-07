# DFlowP

## Framework für datenflussorientierte Programmierung

Bitte hilf mir, mein Python‑Framework zu entwickeln. Das Framework soll datenflussorientierte Programmierung (DFlowP) heißen.

Die datenflussorientierte Programmierung (DFlowP) soll helfen, daten-, rechen- und damit kostenintensive Anwendungen zukunftsfähig zu gestalten, indem die Daten migrierbar und bei Softwarefehlern neukalkulierbar sind.

Dies wird durch Monitoring des Datenflusses sowie Zwischenspeicherung der einzelnen Daten erreicht. 

Damit kann man Software‑Migrationen durchführen und dann die Daten basierend auf der neuen Version aktualisieren sowie bei Softwarefehlern an einer bestimmten Stelle erneut fortfahren.

Die Basis des Frameworks für datenflussorientierte Programmierung soll eine Event Driven Architecture im Backend sein.

Per Server-Client-Architektur soll im Frontend die Ausführung verwaltet werden.

### Beschreibung des Problems

Im Laufe der Entwicklung von datenintensiven Anwendungen kommt man oft an den Punkt, dass die Performance einer Software zu gering ist. 

Dann besteht eine Lösung darin, Optimierungen an einzelnen Softwarekomponenten (hier Teilprozessen) durchzuführen. Dabei kann datenflussorientierte Programmierung helfen, denn durch die Events wird ganz genau mitgeteilt, wie lange ein einzelner Teilprozess zur Bearbeitung der Daten benötigt hat - somit ist einsehbar, welche Softwarekomponente nicht performant ist.

Wenn eine Softwarekomponente ein Update enthält, können Daten in Prozessen einer älteren Version migriert werden.

Bei einigen Vorgängen wie Webscraping sind Softwarefehler ein häufiges Ereignis.

Stürzt die Software bei der Verarbeitung von Daten ab, kann datenflussorientierte Programmierung helfen, an der Stelle, wo die Software abgestürzt ist, mit der Verarbeitung der Daten fortzufahren.

Bei AI-Workflows kann es zwischen einzelnen Konfigurationen wie die des LLM oder der Embedding Engine zu Qualitätsunterschieden kommen.

Ist die Datenqualität nicht ausreichend, können Prozesskonfigurationen wie z. B. die Embedding Engine, die Prompt-Templates oder das LLM per Parameter ausgetauscht werden und damit einzelne Teilprozesse erneut ausgeführt werden.

## Prozesse in DFlowP

In der datenflussorientierten Programmierung unterscheidet man zwischen Input- und Output-Daten.

Welchen Weg die Daten in der datenflussorientierten Programmierung nehmen, wird im Prozess festgelegt. Dieses Attribut im Prozess nennt sich DataFlow. 

Der DataFlow ist eine baumartige Struktur, welche beschreibt, welche Teilprozesse wann im Prozess Daten verarbeiten.

Ein Prozess besteht aus folgenden Attributen: 

- eine ProzessID, welche den Prozess eindeutig identifiziert

- Die Softwareversion, die entscheidend ist, weil sich die Software mit der Zeit weiterentwickelt und dabei auch Daten potenziell migriert werden müssen

- der Prozesskonfiguration - je nach Software können hier verschiedene Parameter wie AI-Models, Schwellenwerte, Embedding-Engines, API-Provider pro Prozess angepasst werden

- Der DataFlow besteht aus den Teilprozessen. 

- Die Teilprozesse, welche die Daten durchlaufen. Diese sind feste Software‑Module, die Input‑Daten annehmen und Output‑Daten ausgeben.

- Der Status des Prozesses, wenn der letzte Teilprozess im DataFlow den Status 'completed' hat, dann ist der komplette Prozess ebenfalls beendet.

- Prozessklone: manchmal ist es notwendig ein Prozess oder einen Teil zu klonen um z. B. einige Teilschritte mit einer neuen Prozesskonfigurationen also z. B. einen anderen LLM zu testen -> auf diese wird hier referenziert

### Teilprozesse

- Teilprozesse arbeiten mit Events, um ihren aktuellen Status bzw. Fortschritt mitzuteilen

- Sie verarbeiten Daten, bekommen also Inputdaten und geben Outputdaten aus

- Sie sind voneinander abgekapselt und bearbeiten Daten asynchron

- Wenn von Teilprozessen abgeleitete Softwarekomponenten in der Ausführung innerhalb eines Prozesses abstürzen, dann wird automatisch das EVENT_FAILED ausgelöst
  
  Teilprozesse können im DataFlow der DFlowP Anwendung überwacht werden

#### Beispiele für Teilprozesse

- Embedden von Daten

- Web-Scraping einer Liste aus dem Internet

- Starten einer AWS Instanz

- Bearbeiten von Daten durch einen RAG-Workflow

- Transkription

- Statusbenachrichtigungen an Clients

#### Implementierung von Teilprozessen

- es existieren TeilprozessID - zur eindeutigen Identifizierung eines Teilprozesses pro Prozess

- eine TeilprozessInstanz-ID – falls später mehr Instanzen eines Teilprozesses zur parallelisierten Verarbeitung gespawnt werden sollen (noch nicht genutzt)

- ein Teilprozesstyp, welcher definiert was für eine Softwarekomponente hier überhaupt ausgeführt werden soll

- das EVENT_STARTED soll automatisch ausgelöst werden, EVENT_COMPLETED ebenfalls

- bei Programmabsturz soll EVENT_FAILED vom DFlowP Framework automatisch ausgelöst werden

### Events

Folgende Events sollen zunächst implementiert werden:

- EVENT_STARTED - ein Teilprozess wurde gestartet

- EVENT_COMPLETED - ein Teilprozess ist komplett beendet

- EVENT_FAILED - ein Teilprozess ist abgestürzt oder fehlgeschlagen - das übergeordnete Framework regelt die Auslösung des Events, falls die Softwarekomponente dies nicht mehr selber tun kann

- noch nicht implementiert: EVENT_PROGRESS - es gibt einen Fortschritt bei der Verarbeitung von Daten im Teilprozess. Hier sollte neben Logs auch die optionale Angabe von Fortschritten in Prozent oder Bruchteilen z. B. 1/88 speicherbar sein

- noch nicht implementiert: EVENT_LOG - eine Logmeldung des Teilprozesses mit unterschiedlichen typischen Logstufen bei Logging z. B. Verbose, Debug, Error

Jedes Event enthält außerdem immer die zugehörige ProzessID, eine TeilprozessID, ggf. eine Teilprozessinstanz ID (Standardmäßig 1) , eine event_time - wann das Event ausgelöst wurde.


Beispielablauf:

1. Prozesskonfiguration festlegen inkl. DataFlow

2. process_engine subscribes alle Events beim EventService, um Subprozesse bzw. Aufgaben aneinander zu verketten sowie über die Fertigstellung einzelner Subprozesse informiert zu werden

3. process_engine erstellt aus der Prozesskonfiguration und dem DataFlow den Kontext für die zuerst zu startenden Subprozesse

4. die process_engine erstellt den dataflow_state innerhalb des process_state, der zunächst leer ist

5. Die Subprozesse werden gestartet und die Elternklasse der Subprozesse löst das Event EVENT_STARTED beim Event Service aus

6. Die Subprozesse verarbeiten Daten und aktualisieren kontinuierlich den dataflow_nodestate im dataflow_state des process_state (z. B. bei jedem abgearbeiteten Item)

7. Bei Fertigstellung der Aufgabe löst der Subprozess das EVENT_COMPLETED beim Eventservice aus

8. Der EventService published über den Eventbus die Fertigstellung des Subprozesses, womit der nächste Subprozess im DataFlow ausgeführt wird

9. Sind alle Subprozesse EVENT_COMPLETED, wird die process_engine vom EventService benachrichtigt und vermerkt den Prozess als EVENT_COMPLETED


Noch ein paar Fragen zu den Daten:

- Wer legt die Qualitätskriterien/Spezifikationen von io_transformationen fest? (Das Plugin für den Subprozess gibt die Kriterien/Spezifikation vor)

- Referenzierung von Daten (IDs) aus der Datenbank (die abstrakte Datenklasse data.py referenziert auf Einträge in der Datenbank, womit ein Dataset immer auch alle Referenzen enthält)

- ProzessID + NodePath im DataFlow + InputdatenID identifiziert die io_transformation bzw. die Outputdaten


Die Ordnerstruktur:

```
dflowp/
├── api/
│   ├── routes/
│   │   ├── processes.py - Schnittstellen zum Starten eines Prozesses mit einer Prozesskonfiguration und zum Abfragen des Prozess-Status
│   │   └── data.py - Lesen von Input- oder Output-Daten
│   └── server.py - Zum Start aller API-Schnittstellen
│
├── core/
│   ├── engine/
│   │   ├── process_engine.py - Prozessengine zur Ausführung, Verwaltung und Überwachung aller Prozesse
│   │   └── runtime.py - Hauptprogramm zum Starten aller benötigten Komponenten
│   ├── events/
│   │   ├── event_bus.py - Kommunikation des Event-Systems inkl. persistenter Speicherung
│   │   ├── event_types.py - Alle Typen von Events
│   │   └── event_service.py - Grundlegende Funktionen (Emit, Subscriben)
│   ├── processes/
│   │   ├── process.py - Abstrakte Implementation eines Prozesses
│   │   ├── process_configuration.py - Konfiguration für den Prozessstart
│   │   └── process_state.py - Metadaten zum Prozess-Status und Dataflow-State
│   ├── subprocesses/
│   │   ├── subprocess.py - Abstrakte Implementation eines Subprozesses
│   │   ├── subprocess_context.py - Kontext für Subprozess (Prozesskonfiguration + Input-Daten)
│   │   └── io_transformation_state.py - Status der Input-Output-Transformation und Qualitätsbewertung
│   ├── datastructures/
│   │   ├── data.py - Datenklasse mit ID zur Lokalisierung in der Datenbank
│   │   └── dataset.py - Mengen von Daten, referenzieren auf Dataset in der Datenbank
│   └── dataflow/
│       ├── dataflow.py - Beschreibt Ablauf (z. B. Scraping -> Embedding -> Clustering)
│       ├── dataflow_node.py - Datenfluss und Status
│       ├── dataflow_state.py - Alle Datenflüsse im Prozess
│       └── dataflow_parser.py - Parsen eines Datenflusses aus JSON
│
├── plugins/
│   ├── embedding/
│   │   └── embedder.py
│   ├── scraping/
│   │   └── web_scraper.py
│   ├── clustering/
│   │   └── clustering.py
│   └── notification/
│       └── notify_client.py
│
├── infrastructure/
│   ├── database/
│   │   ├── mongo.py
│   │   ├── process_repository.py
│   │   ├── data_repository.py
│   │   ├── dataset_repository.py
│   │   └── event_repository.py
│   └── plugins/
│       └── plugin_loader.py
│
├── examples/
│   ├── inputdata_example.json
│   ├── dataflow_example.json
│   ├── processconfiguration_example.json
│   └── dataflowstate_example.json
│
├── tests/
│   ├── database_test.py
│   ├── eventsystem_test.py
│   └── process_test.py
│
├── utils/
│   └── logger.py
│
└── main.py
```

## Aktuelle Version testen

### Voraussetzungen

- Python 3.10+
- MongoDB (für Datenbankfunktionalität)

### Installation

#### Libraries bauen + installieren (empfohlen)

```bash
./scripts/build_and_install_libraries.sh
```

#### Danach Service-Paket installieren

```bash
pip install -e ".[dev]"
```

#### Mit dem Install-Skript (Ubuntu)

```bash
./install.sh
# Optional mit MongoDB: ./install.sh --with-mongodb
```

#### Manuell

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
./scripts/build_and_install_libraries.sh
pip install -r requirements.txt
pip install -e ".[dev]"
```

### Projektstruktur

- **packages/dflowp-core** – Database, Event-Interfaces, Utilities
- **packages/dflowp-processruntime** – Runtime/Engine, Dataflow, Prozesse, Subprozesse, Plugins
- **dflowp/** – API- und Worker-Services

### Tests

```bash
pytest tests/ -v
```

Hinweis: Für Datenbank-Tests muss MongoDB laufen (localhost:27017).

