# Statische CMake-Kandidatenanalyse

## Ausgangspunkt

Die Cacheprofile werden in dieser Reihenfolge geladen:

1. Blenders `bpy_module.cmake`
2. Blenders `blender_lite.cmake`
3. unser `mesh_export.cmake`

`blender_lite.cmake` deaktiviert bereits den Großteil der optionalen Importer,
Renderer, Simulationen, Audio-/Video-Codecs und Bildformate. Das eigene Profil
schaltet OpenColorIO vorerst wieder ein und deaktiviert zusätzlich die für den
Export bekannten großen Systeme.

## Nicht als Größenhebel verfolgt

- Unteroptionen von Cycles, GHOST, LibMV, TBB, X11 und der Python-Installation
  sind zwar teilweise standardmäßig `ON`, ihre Elternsysteme sind aber bereits
  deaktiviert.
- `WITH_EXPERIMENTAL_FEATURES` wird im Release-Quellstand von Blender 4.5.3 durch
  die oberste CMake-Datei unabhängig vom Cachewert auf `OFF` gesetzt.
- `WITH_LINKER_GOLD` ändert nur das Buildwerkzeug.
- `WITH_ASSERT_ABORT` und `WITH_PYTHON_SECURITY` ändern hauptsächlich Verhalten,
  versprechen aber keine relevante Größenersparnis. Sie bleiben aus Sicherheits-
  und Diagnosegründen unverändert.
- `WITH_CPU_SIMD` wird erst nach Messung betrachtet. Eine Deaktivierung kann
  Laufzeit kosten, ohne zwingend nennenswert Binärgröße zu sparen.

## Isolierte nächste Experimente

1. `mesh_export_no_opengl.cmake` deaktiviert ausschließlich
   `WITH_OPENGL_BACKEND`. Der Quellstand bindet damit unter anderem die
   OpenGL-Funktionen des Python-Moduls `bgl` und entsprechende Backend-Pfade nicht
   ein. Ob ein `bpy` ohne Grafikbackend vollständig initialisiert, entscheidet der
   Writer-/Reader-Test.
2. `mesh_export_no_ocio.cmake` bleibt nur als Hochrisiko-Diagnose erhalten.
   Blender hat OpenColorIO und OpenEXR nach beobachteten Linkfehlern in
   `bpy`/`lite` später ausdrücklich zu Pflichtabhängigkeiten gemacht. Diese
   Variante wird daher nicht automatisch gebaut und zählt nicht zur erwarteten
   Größenersparnis.

Die Varianten werden nicht kombiniert. Zuerst wird das Referenz-Wheel gebaut und
gemessen; danach wird mit der OpenGL-Variante nur eine Ursache verändert. Eine
Variante gilt nur bei erfolgreichem Import sowie getrenntem Writer-/Reader-Test
als zulässig.
