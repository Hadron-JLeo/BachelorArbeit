# Abschlussbericht: minimales `bpy` für den Hyperwürfel-Export

## Ausgewählte Wheels

| Python | Variante | Wheel-Download | Installierter Payload | SHA-256 |
|---|---|---:|---:|---|
| 3.11 | ohne OpenGL | **31.342.629 Byte** | 102.729.860 Byte | `651c74dce5c00b1a822c4ff0d78d6d0cf3904079a78308e171acf28e53629409` |
| 3.12 | ohne OpenGL | **31.349.258 Byte** | 102.740.132 Byte | `1f26833ce95fd2c60f42d9f44b34a97326a3a6246d0b3d177d59fb83e99e2ff5` |

Das Python-3.11-Wheel ist 341.664.380 Byte beziehungsweise 91,6 % kleiner als
das offizielle Wheel mit 373.007.009 Byte. Gegenüber der historischen,
nachträglich gekürzten Referenz mit 232.107.470 Byte spart es 200.764.841 Byte
beziehungsweise 86,5 %.

`bpy` deklariert und benötigt keine zusätzlichen Python-Laufzeitpakete. Im
Hypercube-Projekt kommt in einer leeren Umgebung NumPy 2.0.2 hinzu. Damit beträgt
der gemessene Gesamtdownload 50.877.524 Byte unter Python 3.11 und 50.585.431
Byte unter Python 3.12. Bei bereits vorhandenem NumPy bleibt es bei der
jeweiligen Wheel-Größe.

## Variantenvergleich

| Variante | Wheel | Installiert | Importmedian, fünf frische Prozesse | Ergebnis |
|---|---:|---:|---:|---|
| CPython 3.11, Standard | 31.570.844 Byte | 103.757.884 Byte | 0,201 s | bestanden |
| CPython 3.11, ohne OpenGL | **31.342.629 Byte** | 102.729.860 Byte | 0,162 s | ausgewählt |
| CPython 3.12, Standard | 31.574.866 Byte | 103.759.964 Byte | 0,196 s | bestanden |
| CPython 3.12, ohne OpenGL | **31.349.258 Byte** | 102.740.132 Byte | 0,167 s | ausgewählt |

Alle vier finalen Varianten wurden in zwei separaten GitHub-Actions-Läufen neu
gebaut. Wheel-Größe und SHA-256 waren für jede Variante bytegenau identisch.
Der definitive grüne Lauf ist
[GitHub Actions 35097221024](https://github.com/Hadron-JLeo/BachelorArbeit/actions/runs/35097221024).

## Bestandene Prüfungen

- ZIP-, Metadaten- und vollständige `RECORD`-Integrität des finalen Wheels
- Installation mit `--no-deps`, `pip check` und Import in einer frischen Umgebung
- Import sowie Writer/Reader ohne NumPy oder ein anderes Drittanbieter-Pythonpaket
- Writer und Reader in getrennten Prozessen
- komprimierte und unkomprimierte `.blend`-Dateien
- mehrere vollständige Exporte im selben Interpreterprozess
- Minimal-Writer → offizielles unverändertes `bpy 4.5.3`
- offizieller Writer → Minimal-Reader
- Dreiecke, Quads, konkave N-Ecke, lose Kanten und nicht binär exakt darstellbare Koordinaten
- Collections, Empties, mehrstufige Elternbeziehungen und Transformationen
- Materialien, Principled-BSDF-Farbe, Roughness, eigene Properties, Unicode und Text-Datenblöcke
- Ausführung ohne Display, GPU oder installierte Blender-Anwendung
- Endprüfung in einem zweiten Container ohne Quellen-, Build- oder Stage-Mount
- unabhängiges Protokollgate ohne schwerwiegende Laufzeitfehlermuster

## Reproduzierbare Grundlage

- Blender `v4.5.3`: `67807e1800cc48cc7bff3c793525e1179a4d64ca`
- Blender-Linux-Bibliotheken: `c1b8027b12441d29b9a344c3f1524d3ce9fa127d`
- Container: `manylinux_2_28_x86_64`, Digest
  `sha256:531d7aa844bbb0c131d4ab011d3db741c4abc8d498cd5ccc86121046f62303b4`
- deterministischer Zeitstempel: `SOURCE_DATE_EPOCH=1757335597`
- Paketindex für die protokollierten Python-Werkzeuge: `https://pypi.org/simple`
- exakte Python-Buildwerkzeugversionen und effektive CMake-Optionen liegen in den Release-Belegen

Angenommen wurden insbesondere die native ELF-Abhängigkeitsclosure, das Entfernen
nicht benötigter Core-Add-ons, Presets, optionaler Assets, UI-Schriften und
generierter Bytecode-Caches sowie `strip --strip-unneeded` ausschließlich auf
erkannten ELF-Dateien. OpenColorIO und die für einen fehlerfreien Start nötigen
Core-Add-ons blieben erhalten. Zopfli/DEFLATE-15 lieferte das kleinste weiterhin
direkt durch `pip` installierbare Wheel.

## Linux-Laufzeitabhängigkeiten

Mitgeliefert werden:

- `libIex.so.32`, `libIlmThread.so.32`, `libImath.so.30`
- `libOpenColorIO.so.2.4`
- `libOpenEXR.so.32`, `libOpenEXRCore.so.32`
- `libOpenImageIO.so.3.0`, `libOpenImageIO_Util.so.3.0`
- `libtbb.so.12`

Als Systembibliotheken werden nur der Linux-Loader sowie `libatomic`, `libc`,
`libdl`, `libgcc_s`, `libm`, `libpthread`, `libstdc++` und `libutil` verwendet.
`auditwheel` bestätigt den Tag `manylinux_2_28_x86_64`; es sind keine separaten
Desktop-, X11-, OpenGL- oder Blender-Laufzeitdownloads erforderlich.

## Voraussetzungen und Grenzen

Unterstützt werden Linux x86_64, glibc 2.28 oder neuer und exakt CPython 3.11
beziehungsweise 3.12. Das Wheel ist ein inoffizieller, eingeschränkter
Export-Build mit der Version `4.5.3+mesh1`, kein vollständiger Blender-Ersatz.

OpenGL-Backend, Rendering, Simulation, Audio/Video, Asset-Browser, UI-Textanzeige
und Import/Export fremder Dateiformate gehören nicht zum zugesagten Umfang. Die
entfernten UI-Schriften verursachen erwartete Font-Warnungen beim Start, jedoch
keinen Fehler des abgesicherten Exportvertrags. Python 3.12 ist ein zusätzlich
für dieses Projekt gebauter und geprüfter Port. Die Auswahl ist die kleinste
bestandene der konkret untersuchten Varianten und keine Behauptung theoretischer
globaler Minimalität.
