# Minimales `bpy` für den Hyperwürfel-Export

Dieses Verzeichnis enthält eine reproduzierbare Build- und Prüfstrecke für ein
auf den benötigten Mesh- und `.blend`-Export reduziertes `bpy`. Das Wheel ist
bewusst vom Python-Paket in `imports/` getrennt und kein vollständiger Ersatz
für Blender.

## Projektmodule im Notebook installieren

Die Paketmetadaten liegen im Wurzelverzeichnis des Repositories. Daher wird das
Repository ohne `#subdirectory=imports` installiert:

```python
%pip install --upgrade --no-cache-dir \
  "hypercube-graph-surface @ git+https://github.com/Hadron-JLeo/BachelorArbeit.git@main"
```

Das vorbereitete Notebook
[`notebooks/minimal_bpy_colab.ipynb`](notebooks/minimal_bpy_colab.ipynb) wählt
das passende Linux-Wheel für Python 3.11 oder 3.12, prüft vor der Installation
seine SHA-256-Summe und erzeugt anschließend eine kleine `.blend`-Datei.

## Abgesicherter Umfang

Der Test bildet den tatsächlich benötigten Notebook-Vertrag ab:

- Meshes mit losen Kanten, Dreiecken, Quads und konkaven N-Ecken
- Collections, Empty-Objekte und mehrstufige Eltern-Kind-Beziehungen
- Transformationen, Auswahl, Anzeigeattribute und eigene Properties
- Materialien einschließlich Principled-BSDF-Farbe und Roughness
- Text-Datenblöcke, Unicode sowie `mathutils.Vector` und `Quaternion`
- komprimiertes und unkomprimiertes Speichern von `.blend`-Dateien
- mehrere Exporte in einem langlebigen Python-Prozess

Writer und Reader laufen jeweils in getrennten Prozessen. Zusätzlich liest das
offizielle unveränderte `bpy 4.5.3` die Datei des Minimal-Writers und der
Minimal-Reader die Datei des offiziellen Writers. Der genaue Vertrag steht in
[`API_CONTRACT.md`](API_CONTRACT.md).

Rendering, Simulation, Audio/Video, Asset-Browser, Benutzeroberfläche und der
Import oder Export fremder Dateiformate gehören ausdrücklich nicht zum
zugesagten Umfang. Die von Blender beim sauberen Start erwarteten Core-Add-ons
bleiben erhalten; weitere Core-Add-ons werden einzeln als Kürzungskandidat
geprüft.

## Reproduzierbarer Build

Der Workflow
[`build-minimal-bpy.yml`](../.github/workflows/build-minimal-bpy.yml) baut vier
isolierte Kandidaten:

- CPython 3.11 mit dem Standard-Minimalprofil
- CPython 3.11 ohne OpenGL-Backend
- CPython 3.12 mit dem Standard-Minimalprofil
- CPython 3.12 ohne OpenGL-Backend

Fixierte Grundlage:

- Blender `v4.5.3`, Commit `67807e1800cc48cc7bff3c793525e1179a4d64ca`
- Blender-Linux-Bibliotheken, Commit
  `c1b8027b12441d29b9a344c3f1524d3ce9fa127d`
- NumPy `2.0.2` für den gemeinsamen Projekttest
- exakt festgeschriebene Python-Buildwerkzeuge; verwendeter Paketindex
  `https://pypi.org/simple`
- `manylinux_2_28_x86_64`, Container-Digest
  `sha256:531d7aa844bbb0c131d4ab011d3db741c4abc8d498cd5ccc86121046f62303b4`
- reproduzierbarer Zeitstempel `SOURCE_DATE_EPOCH=1757335597`

Zuerst entsteht ein getestetes Referenz-Wheel. Danach werden installierte
Laufzeitbestandteile einzeln entfernt. Eine Kürzung wird nur übernommen, wenn
Import, Writer, Reader und Mehrfachexport weiterhin bestehen und das Protokoll
keine schwerwiegenden Laufzeitfehler enthält. Native Bibliotheken werden auf die
tatsächliche ELF-Abhängigkeitskette reduziert; danach werden die Binärdateien
gestrippt, doppelte generierte Python-Bytecode-Caches entfernt und das Wheel
deterministisch neu komprimiert.

Die abschließende Prüfung läuft in einem zweiten Container, der keinen Zugriff
auf Quellen, Buildverzeichnis oder Stage-Verzeichnis besitzt. Sie umfasst:

- vollständige ZIP- und `RECORD`-Integritätsprüfung
- Import und Writer/Reader in einem venv ohne Drittanbieter-Pythonpakete
- Installation mit `--no-deps`, `pip check` und NumPy 2.0.2
- den kompletten Writer-/Reader-Vertrag in frischen Prozessen
- gegenseitiges Lesen mit dem offiziellen `bpy 4.5.3`
- fünf frische Importprozesse für die Laufzeitmessung
- Erfassung von Downloadgröße, installiertem Payload und ELF-Abhängigkeiten

Nach Veröffentlichung führt der separate Workflow
[`verify-minimal-bpy-notebook.yml`](../.github/workflows/verify-minimal-bpy-notebook.yml)
das Release-Notebook außerdem vollständig in echten Jupyter-Kerneln für Python
3.11 und 3.12 aus. Die dabei erzeugte Datei wird anschließend in einem zweiten
Python-Prozess geöffnet und inhaltlich geprüft.

Große Quellen, Buildverzeichnisse, Protokolle und Wheels werden nicht in Git
gespeichert. GitHub Actions stellt sie vorübergehend als Build-Artefakte bereit;
die ausgewählten geprüften Wheels und Berichte werden dauerhaft als
GitHub-Release veröffentlicht.

## Selbst bauen

Der Build ist für GitHub Actions auf Ubuntu 24.04 ausgelegt. Er lässt sich über
**Actions → Build and verify minimal bpy → Run workflow** auf dem Branch
`codex/minimal-bpy` starten. Jeder Matrix-Job erzeugt neben dem Wheel einen
`BUILD_REPORT.md`, strukturierte JSON-/CSV-Messdaten und sämtliche
Validierungsprotokolle.

Die CMake-Entscheidungen und bewusst nicht kombinierten Experimente sind in
[`CMAKE_MINIMIZATION.md`](CMAKE_MINIMIZATION.md) dokumentiert.
Alle Änderungen an Blenders Quellen beziehungsweise installierten Startskripten
sind zusätzlich als lesbare Dateien unter [`patches/`](patches/) abgelegt.
