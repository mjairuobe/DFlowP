# ToDos

- Ich möchte, dass im Output‑Datensatz vom Embed‑Data‑Plugin unter "content" und dem Subkey "text" nicht die ersten 500 Zeichen des Textes gespeichert werden, sondern ein F‑String, der auf den Attributen des Artikels der Input‑Daten basiert. In diesem Beispiel wäre es {title} {summary}. Damit kann ich die Daten besser reproduzieren und habe eine konsistentere Software.
  Erzeuge den Wert dieses Feldes gerne dynamisch und füge entsprechende Kommentare hinzu, um die Funktionsweise und den Nutzen transparent zu machen.
  Gebe mir zudem ein Command für die Shell, um mit mongod alle bisherigen Datensätze dementsprechend zu migrieren

- Weitere Änderungen am Datenbankschemata vornehmen
  
- Ich möchte den Dataflow in der Datenbank gespeichert haben.
  
- Ich möchte die Prozesskonfiguration in der Datenbank gespeichert haben.
  
- Ich möchte alle Dataflow-States, also inklusive aller IO-Transformations-States, in der Datenbank gespeichert haben
  
- Die Dokumente im Prozesskonfigurationsrepository sollen die Dataflow‑Dokumente mit einer ID referenzieren.
  
- Die Dokumente im Prozesskonfigurationsrepository sollen die Dataflow‑State-Dokumente mit einer ID referenzieren
  
- Die Dokumente im DataFlowStateRepository sollen alle IO-Transformation-States mit einer ID referenzieren.
  
- Ich möchte Prozesse klonen können und diese mit anderen Konfigurationen erneut starten, wobei nur ein Teil der Subprozesse erneut ausgeführt werden muss. Dabei soll einfach ein neuer Prozess erstellt werden, mit einer neuen Prozesskonfiguration, die auf einen neuen Dataflow zeigt, und dabei den alten Dataflow‑State kopiert und als Basis verwendet. Die Data, Datasets und IO‑Transformationsstates bleiben unberührt, werden aber nun von den Daten des neuen Prozesses referenziert.