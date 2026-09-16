# Minimaler bpy-Build

Dieses Verzeichnis enthält die reproduzierbare Build-Umgebung für ein auf den
Mesh- und `.blend`-Export reduziertes `bpy`. Es ist bewusst vom Python-Paket in
`imports/` getrennt.

Der Workflow `.github/workflows/build-minimal-bpy.yml` baut zuerst eine
getestete Referenz. Danach entfernt er installierte Laufzeitbestandteile
schrittweise. Jede einzelne Kürzung wird nur übernommen, wenn Import, Writer und
Reader in jeweils neuen Python-Prozessen erfolgreich sind. Abschließend wird das
Wheel in einer sauberen Umgebung zusammen mit dem im Hauptprojekt verwendeten
NumPy 2.0.2 installiert und erneut vollständig geprüft.

Fixierte Grundlage:

- Blender `v4.5.3`, Commit `67807e1800cc48cc7bff3c793525e1179a4d64ca`
- Linux-Bibliotheken, Commit `c1b8027b12441d29b9a344c3f1524d3ce9fa127d`
- CPython 3.11
- `manylinux_2_28_x86_64`, auf einen festen Container-Digest fixiert

Große Quellen, Buildverzeichnisse, Protokolle und Wheels werden nicht ins
Repository aufgenommen. Der Workflow stellt Referenz- und Minimal-Wheel,
SHA-256, exakte Download-/Installationsgröße, die tatsächlich benötigte
ELF-Bibliothekskette und alle Prüfprotokolle als kurzlebiges GitHub-Artefakt
bereit.
