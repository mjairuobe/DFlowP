# DFlowP

## Framework für datenflussorientierte Programmierung

Bitte hilf mir, mein Python‑Framework zu entwickeln. Das Framework soll datenflussorientierte Programmierung (DFlowP) heißen.

Die datenflussorientierte Programmierung (DFlowP) soll helfen daten, rechen- und damit kostenintensive Anwendungen zukunftsfähig zu gestalten, indem die Daten migrierbar und bei Softwarefehler neukalkulierbar sind.

Dies wird durch Monitoring des Datenflusses sowie Zwischenspeicherung der einzelner Daten erreicht. 

Damit kann man Software‑Migrationen durchzuführen und dann die Daten basierend auf der neuen Version aktualisieren, sowie bei Softwarefehlern an einer bestimmten Stelle erneut fortfahren.

Die Basis des Frameworks für datenflussorientierte Programmierung soll eine Event Driven Architecture im Backend sein.

Per Server-Client-Architektur soll im Frontend die Ausführung verwalten werden.

### Beschreibung des Problems

Im Laufe der Entwicklung von datenintensiven Anwendungen kommt man oft an den Punkt, dass die Performance einer Software zu gering ist. 

Dann ist eine Lösung Optimierungen an einzelnen Softwarekomponenten (hier Teilprozessen) durchzuführen. Dabei kann datenflussorientierte Programmierung helfen, denn durch die Events wird ganz genau mitgeteilt, wie lange ein einzelner Teilprozess zur Bearbeitung der Daten benötigt hat - somit ist einsehbar, welche Softwarekomponente nicht performant ist.

Wenn eine Softwarekomponente ein Update enthält, dann können Daten in Prozessen einer älteren Version, migriert werden

Bei einigen Vorgängen wie Webscraping sind Softwarefehler eine häufiges Ereignis.

Stützt die Software bei der Verarbeitung von Daten ab, kann datenflussorientierte Programmierung helfen, an der Stelle, wo die Software abgestürzt ist, mit der Verarbeitung der Daten fortzufahren.

Bei AI-Workflows kann es zwischen einzelnen Konfigurationen wie die des LLM oder der Embedding Engine zu Qualitätsunterschieden kommen.

Ist die Datenqualität können Prozesskonfigurationen wie z. B. die Embedding Engine, die Prompt-Templates oder das LLM per Parameter ausgetauscht werden und damit einzelne Teiprozesse erneut ausgeführt werden.

## Prozesse in DFlowP

In der datenflussorientierten Programmierung unterscheidet man zwischen Input- und Output-Daten.

Welchen Weg die Daten in der datenflussorientierten Programmierung nehmen, wird im Prozess festgelegt. Dieses Attribut im Prozess nennt sich DataFlow. 

Der DataFlow ist eine baumartige Struktur, welche beschreibt, welche Teilprozesse wann im Prozess Daten verarbeiten.

Ein Prozess besteht aus folgenden Attributen: 

- eine ProzessID, welche den Prozess eindeutig identifiziert

- Die Softwareversion, die entscheidend ist, weil sich die Software mit der Zeit weiterentwickelt wird und dabei auch Daten potentiell migriert werden müssen

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

- eine TeilprozessInstanz ID - falls später mehr Instanzen eines Teilprozesses zur paralellisierten Verarbeitung gespawnt werden sollen (noch nicht genutzt)

- ein Teilprozesstyp, welcher definiert was für eine Softwarekomponente hier überhaupt ausgeführt werden soll

- das EVENT_STARTED soll automatisch ausgelöst werden, EVENT_COMPLETED ebenfalls

- bei Programmabsturz soll EVENT_FAILED vom DFlowP Framework automatisch ausgelöst werden

### Events

Folgende Events sollen zunächst implementiert werden:

- EVENT_STARTED - ein Teilprozess wurde gestartet

- EVENT_COMPLETED - ein Teilprozess ist komplett beendet

- EVENT_FAILED - ein Teilprozess ist abgestürzt oder fehlgeschlagen - das übergeordnete Framework regelt die Auslösung des Events, falls die Softwarekomponente dies nicht mehr selber tun kann

- noch nicht implementieren: EVENT_PROGRESS - es gibt einen Fortschritt bei der Verarbeitung von Daten im Teilprozess. Hier sollte neben Logs auch die optionale Angabe von Fortschritten in Prozent oder Bruchteilen z. B. 1/88 speicherbar sein

- noch nicht iplementieren: EVENT_LOG - eine Logmeldung des Teilprozesses mit unterschiedlichen typischen Logstufen bei Logging z. B. Verbose, Debug, Error

Jedes Event enthält außerdem immer die zugehörige ProzessID, eine TeilprozessID, ggf. eine Teilprozessinstanz ID (Standardmäßig 1) , eine event_time - wann das Event ausgelöst wurde.


Beispielablauf:

1. Prozesskonfiguration festlegen inkl. DataFlow

2. process_engine subscribte alle Events beim EventService, um Subprozesse bzw. Aufgaben anneinander zu verketten, sowie über die Fertigstellung einzelner Subprozesse informiert zu werden

3. process_engine erstellt aus der Prozesskonfiguration und den DataFlow den Kontext für die zu erst zu startenden Subprozesse

4. die process_engine erstellt den dataflow_state innerhalb des process_state, der zunächst leer ist

5. Die Subprozesse werden gestartet und die Elternklasse der Subprozesse löst emitted das Event EVENT_STARTED beim Event Service

6. Die Subprozesse verarbeiten Daten und aktualisieren kontinulierlich den dataflow_nodestate im dataflow_nodestate des process_state (z. B. bei jeden abgearbeiteten Item)

7. Bei Fertigstellung der Aufgabe löst der Subprozess das EVENT_COMPLETED beim Eventservice aus

8. Der EventService published über den Eventbus die Fertigstellung des Subprozesses, womit der nächste Subprozess im DataFlow ausgeführt wird

9. Sind alle Subprozesse EVENT_COMPLETED wird die process_engine ausgelöst vom EventService den Prozess als EVENT_COMPLETED vermerken


Ein paar mehr Daten Fragen:

- wer liegt die Qualitätkriterien/spezifikationen von io_transformationen fest? (Das Plugin für den Subprozess gibt die Kriterien/Spezifikation vor)

- Referenzierung von Daten (IDs) aus der Datenbank (die abstrakte Datenklasse data.py referenziert etwas aus der Datenbank, womit ein dataset immer auch alle Referenzen enthält.

- ProzessID + NodePath im DataFlow + InputdatenID identifiziert die io_transformation bzw. die Outputdaten


Die Ordnerstruktur:

dflowp/
│
├── api/
│   ├── routes/
│   │   ├── processes.py - Schnittstellen zum Starten eines Prozesses mit einer Prozesskonfiguration und zum Abfragen der Prozess Status
│   │   └── data.py - Lesen von Input- oder Output-Daten.
│   │
│   └── server.py - Zum Start aller API‑Schnittstellen.
│
├── core/
│   ├── engine/
│   │   ├── process_engine.py - Prozessengine, die zur Ausführung, Verwaltung und Überwachung aller Prozesse verantwortlich ist.
│   │   └── runtime.py - Hauptprogramm zum Starten aller benötigten Komponenten in der Core Application.
│   │
│   ├── events/
│   │   ├── event_bus.py - Kommunikation des Event-Systems inklusive persistente Speicherung in der Datenbank.
│   │   ├── event_types.py - Alle Typen von Events
│   │   └── event_service.py - Die grundlegenden Funktionen des Event-Systems wie Emit, Subscriben.
│   │
│   ├── processes/
│   │   ├── process.py - Abstrakte Implementation eines Prozesses.

|   |   ├── process_configuration.py - Die komplette Konfiguration, die ein Prozess beim Starten benötigt
│   │   └── process_state.py - Enthält Metadaten zum Prozess Status und den kompletten Dataflow State
│   │

|   ├── subprocesses/

│   │     ├── subprocess.py - Abstrakte Implementation eines Subprozesses

│   │     ├── subprocess_context.py - enthält den kompletten Kontext, den ein zu startender Subprozess benötigt. Dieser wird aus der Prozesskonfiguration der Hauptprozesses und den Input‑Daten der vorherigen Subprozesse zusammengesetzt.

|   |     ├── io_transformation_state.py - Enthält den Status der Transformation von den einzelnen Input-Daten zu Output-Daten, inklusive eine Bewertung der Qualität der Transformation



|   ├── datastructures/

│   │    ├── data.py - Übergeordnete Datenklasse, die auch eine ID zur Lokalisierung der Daten innerhalb der Datenbank enthält

|    |    ├── dataset.py - Enthält Mengen von Daten (data.py) ohne Ordnung, welche ebenfalls auf das Dataset in der Datenbank referenziert



│   └── dataflow/

│       ├── dataflow.py - Datenstruktur, die beschreibt, wann welcher Subprozess ausgeführt werden soll, ist also unabhängig von einer konkreten Ausführung z. B. Scraping -> Embedding - Clustering -> Notification

│       ├── dataflow_node.py - enthält einen Datenfluss (io_transformation_state) und den Status (Fehler, noch nicht gestartet, fertig)

|       ├── dataflow_state.py - enthält alle Datenflüsse (dataflow_node) im gesamten Prozess

│       └── dataflow_parser.py - zum Parsen eines Datenflows aus einer JSON Darstellung
│
├── plugins/
│   ├── embedding/
│   │   └── embedder.py - Embedding eines Input datasets
│   │
│   ├── scraping/
│   │   └── web_scraper.py
│   │
│   ├── clustering/
│   │   └── clustering.py
│   │
│   └── notification/
│       └── notify_client.py
│
├── infrastructure/
│   ├── database/
│   │   ├── mongo.py
│   │   ├── process_repository.py - Repository von allen Prozessen, inklusive deren Konfigurationen

│   │   ├── data_repository.py - Repository für alle Input- und Output-Daten

│   │  ├── dataset_repository.py - Repository, dass Daten miteinander gruppiert z. B. einzelne Inputdaten

│   │   └── event_repository.py - Repository von allen Events
│   │
│   │
│   └── plugins/
│       └── plugin_loader.py - Ladet alle Plugins zur Verwendung.
│
├── examples/

|   ├──  inputdata_example.json - Beispiel Input‑Daten eines Subprozesses.
│   ├── dataflow_example.json - Beispiel Datenfluss für eine Prozesskonfiguration.
│   ├── processconfiguration_example.json - Beispiel Prozesskonfiguration

│   └── dataflowstate_example.json - Beispiel eines States der Prozessdatenflüsse.
│
├── tests/
│   ├── database_test.py - Testet, ob in die Datenbank geschrieben und davon gelesen werden kann (in allen Repositories)
│   ├── eventsystem_test.py- Testet das Eventsystem
│   └── process_test.py - Testet einen kompletten Prozess, das heißt, Konfiguration mit Dataflow, Prozessen und Datenbank zusammen.
│
├── utils/
│   └── logger.py - Logging in the software
│
└── main.py



## Aktuelle Version testen

### Voraussetzungen

- Python 3.10+
- MongoDB (für Datenbankfunktionalität)

### Installation

#### Mit pip

```bash
pip install -e .
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
pip install -r requirements.txt
```

### Projektstruktur

- **dflowp/core** – Events, Engine, Processes
- **dflowp/infrastructure** – Datenbankrepositories (MongoDB)
- **dflowp/utils** – Logger und Hilfsfunktionen

### Tests

```bash
pytest tests/ -v
```

Hinweis: Für Datenbank-Tests muss MongoDB laufen (localhost:27017).

## Lizenz

Siehe [LICENSE](LICENSE) falls vorhanden.
