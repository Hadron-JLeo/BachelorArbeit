# Minimaler bpy-Build

Dieses Verzeichnis enthält die reproduzierbare Build-Umgebung für ein auf den
Mesh- und `.blend`-Export reduziertes `bpy`. Es ist bewusst vom Python-Paket in
`imports/` getrennt.

Der Workflow `.github/workflows/build-minimal-bpy.yml` wird ausschließlich
manuell gestartet. Der erste Lauf erzeugt zunächst eine getestete Referenz. Erst
danach werden Funktionen und Bibliotheken schrittweise entfernt; nach jeder
Änderung müssen Writer und Reader in getrennten Python-Prozessen erfolgreich
bleiben.

Fixierte Grundlage:

- Blender `v4.5.3`, Commit `67807e1800cc48cc7bff3c793525e1179a4d64ca`
- Linux-Bibliotheken, Commit `c1b8027b12441d29b9a344c3f1524d3ce9fa127d`
- CPython 3.11
- `manylinux_2_28_x86_64`

Große Quellen, Buildverzeichnisse, Protokolle und Wheels werden nicht ins
Repository aufgenommen. Der Workflow stellt das erzeugte Wheel zusammen mit den
Prüfberichten als kurzlebiges GitHub-Artefakt bereit.
