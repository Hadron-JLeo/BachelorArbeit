# API-Vertrag für den Hyperwürfel-Export

Quelle dieses Vertrags ist der tatsächlich ausgeführte Blender-Code aus Abschnitt
7.2 von `Hypercube-graph-sept.ipynb`. Der aktuelle `main`-Stand des
GitHub-Repositories enthält diesen Export noch nicht; dort werden bislang nur
NumPy, Open3D und Plotly verwendet.

Ein verkleinertes `bpy` ist für dieses Projekt nur brauchbar, wenn der Export in
einem frischen Python-Prozess eine `.blend`-Datei schreiben und ein zweiter
frischer Prozess sie wieder vollständig lesen kann.

## Benötigte Python-Schnittstellen

- `bpy.app.background` und `bpy.app.version_string`
- `bpy.ops.wm.read_factory_settings`, `save_as_mainfile` und `open_mainfile`
- `bpy.context.scene`, `view_layer`, `preferences` und aktive Objekte
- `bpy.data.collections`, `objects`, `meshes`, `materials`, `texts` und `screens`
- Verknüpfen von Collections und Objekten
- Mesh-Erzeugung über `Mesh.from_pydata` und `Mesh.update`
- N-Ecke ohne vorherige Triangulierung
- Empty-Objekte und mehrstufige Eltern-Kind-Beziehungen
- Objekttransformationen, Auswahl, Anzeigeattribute und benutzerdefinierte
  Properties einschließlich Zeichenketten, Zahlen und Unicode
- Materialzuweisung, `use_nodes`, Principled-BSDF-Farbe und Roughness
- Text-Datenblöcke mit eingebetteten JSON-Quelldaten und Bedienhinweisen
- `mathutils.Vector` und `mathutils.Quaternion`
- Zugriff auf View3D-Shading und `RegionView3D`, sofern im Hintergrundprozess ein
  entsprechender Screen existiert
- Setzen von `preferences.filepaths.save_version`

## Dateivertrag

- Exakte Objekt-, Mesh-, Material-, Collection- und Elternstruktur bleibt nach
  erneutem Öffnen erhalten.
- Freie Ränder, lose Kanten, Dreiecke, Quads und konkave N-Ecke bleiben gültig.
- Transformationen, Materialparameter, Properties, Unicode und Text-Datenblöcke
  bleiben erhalten.
- Writer und Reader laufen getrennt, damit kein In-Memory-Zustand den Test
  verfälscht.
- Mindestens unkomprimiertes und komprimiertes Speichern werden geprüft, auch wenn
  der aktuelle Notebook-Export standardmäßig unkomprimiert speichert.

## Konsequenz für die Minimierung

Der Basistest wurde um Collections, Empty-Hierarchien, Text-Datenblöcke,
Roughness, Anzeigeattribute, Dateieinstellungen sowie `mathutils.Vector` und
`mathutils.Quaternion` erweitert. Damit bildet er den aktuell im Notebook
ausgeführten API-Umfang statisch ab. Verbindlich wird diese Schranke, sobald der
erste Writer-/Reader-Lauf mit dem gebauten Referenz-Wheel bestanden ist.
