
# Hyperwürfelgraphen als Polygonfamilien

Das kurze Notebook [Hypercube-graph-bpy-minimal.ipynb](Hypercube-graph-bpy-minimal.ipynb)
erzeugt für eine gewählte Dimension die Blender-Datei.

[In Google Colab öffnen](https://colab.research.google.com/github/Hadron-JLeo/BachelorArbeit/blob/main/Hypercube-graph-bpy-minimal.ipynb)

## Ablauf

1. Projektmodule installieren.
2. `install_minimal_bpy()` einmal pro frischer Sitzung aufrufen.
3. `main(dimension=4)` ausführen; die Zahl legt die Dimension fest.

```python
from imports.main import main

blend_path = main(dimension=4)
```

Colab startet den Download, lokales Jupyter zeigt einen Dateilink. Die Dateien
werden unter `blender_export/` gespeichert. Gleichnamige Exporte werden ersetzt;
mit `overwrite=False` lässt sich das verhindern. Jeder Aufruf erzeugt seine
Oberfläche neu. Es werden keine vorherigen Notebook-Variablen benötigt.
## Module

| Datei | Aufgabe |
|---|---|
| `imports/config.py` | Geometrie- und Darstellungsparameter |
| `imports/model.py` | Polygon-Datenmodell |
| `imports/geometry.py` | Geometrische Operationen |
| `imports/construction.py` | Induktive Konstruktion |
| `imports/visualization.py` | Optionale Open3D-/Plotly-Darstellung |
| `imports/bpy_setup.py` | Wheel-Auswahl, SHA-256-Prüfung und Installation |
| `imports/blender_export.py` | Blender-Szene, Hierarchien und Export |
| `imports/main.py` | Konstruktion, Export und Download in einem Aufruf |

## Voraussetzungen

Die veröffentlichten Minimal-bpy-Wheels unterstützen Linux x86_64, glibc 2.28
oder neuer sowie CPython 3.11 und 3.12. Für Python 3.13 liegt kein passendes
Minimal-Wheel vor. Die Wheels benötigen rund 31,3 MB Download. Die einfache
Blender-Ausgabe benötigt NumPy und Minimal-bpy; Open3D und Plotly gehören zum
optionalen Paket-Extra `visualization`.

Die verfügbaren Wheels und Prüfnachweise liegen im
[Release bpy-mesh-4.5.3.1](https://github.com/Hadron-JLeo/BachelorArbeit/releases/tag/bpy-mesh-4.5.3.1).

## Prüfung

```bash
python -m unittest discover -s tests -v
```

Die Blender-Integrationstests werden ohne installiertes `bpy` übersprungen.
Das Geometrieverfahren und seine Standardparameter wurden bei der Auslagerung
nicht verändert. Die Modularisierung erfolgte mit KI-Unterstützung.
