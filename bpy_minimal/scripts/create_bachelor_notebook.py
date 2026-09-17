"""Generate the complete bachelor-thesis notebook from versioned source cells."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "Hypercube-graph-bpy-minimal.ipynb"


def source(text: str) -> list[str]:
    """Return normalized notebook source lines."""
    normalized = dedent(text).strip("\n") + "\n"
    return normalized.splitlines(keepends=True)


def markdown(cell_id: str, text: str) -> dict:
    return {
        "cell_type": "markdown",
        "id": cell_id,
        "metadata": {},
        "source": source(text),
    }


def code(cell_id: str, text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": cell_id,
        "metadata": {},
        "outputs": [],
        "source": source(text),
    }


cells = [
    markdown(
        "colab-badge",
        """
        <a href="https://colab.research.google.com/github/Hadron-JLeo/BachelorArbeit/blob/main/Hypercube-graph-bpy-minimal.ipynb" target="_parent"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="In Colab öffnen"/></a>
        """,
    ),
    markdown(
        "title",
        r"""
        # Hyperwürfelgraphen als Adjazenzgraphen polyedrischer Oberflächen

        **Bachelorarbeit · modularisierte Exportfassung · 17. September 2026**

        Dieses Notebook erzeugt für eine Dimension $d$ eine Familie konvexer
        Polygone in $\mathbb{R}^3$. Jedem **Polygon** entspricht ein Knoten des
        Hyperwürfelgraphen $Q_d$; jede **gemeinsame vollständige Polygonseite**
        repräsentiert eine Graphkante. Die sichtbaren Polygonecken sind daher von
        den Graphknoten zu unterscheiden.

        Die theoretische Grundlage ist die Konstruktion von McMullen, Schulz und
        Wills, wie sie Arseneva et al. in Abschnitt 3.4, Proposition 3.14,
        darstellen ([Primärquelle](https://doi.org/10.1007/s00454-023-00537-6)).
        Die folgenden Rechenwege erläutern die konkrete Implementierung; die Wahl
        der numerischen Parameter ist eine Implementierungsentscheidung.

        Für $Q_d$ werden $2^d$ Polygone mit jeweils $d+4$ Ecken erwartet. Der
        Graph hat für $d\geq1$ genau $d\,2^{d-1}$ Kanten. $Q_0$ besteht aus einem
        Knoten ohne Kanten und wird hier durch ein einzelnes Quadrat dargestellt.

        Der Geometriekern ist in `config.py`, `model.py`, `geometry.py`,
        `construction.py` und `visualization.py` ausgelagert. Das Notebook lädt
        diese Module aus dem GitHub-Repository. Nur die reproduzierbare Umgebung,
        die konkrete Ausführung und der `.blend`-Export bleiben im Notebook.

        **Lesepfad:** Umgebung → Konfiguration und Mathematik → Konstruktion →
        interaktives Beispiel → direkter Minimal-`bpy`-Export → Einordnung.
        """,
    ),
    markdown(
        "environment",
        r"""
        ## 1. Umgebung und Installation

        Die Zellen werden von oben nach unten in einer frischen Sitzung
        ausgeführt. Unterstützt werden Linux x86_64 mit glibc 2.28 oder neuer und
        CPython 3.11 beziehungsweise 3.12. Google Colab erfüllt diese
        Voraussetzungen. Eine lokale Blender-Installation, ein Display und eine
        GPU sind nicht erforderlich.

        Die erste Zelle installiert die Projektmodule aus dem Wurzelverzeichnis
        des Repositories. Deshalb wird **kein** `#subdirectory=imports` verwendet.
        Das Extra `visualization` ergänzt die bereits vorhandene Open3D-/Plotly-
        Darstellung. `%pip` installiert in den aktiven Notebook-Kernel.
        """,
    ),
    code(
        "install-project",
        """
        %pip install --upgrade --no-cache-dir "hypercube-graph-surface[visualization] @ git+https://github.com/Hadron-JLeo/BachelorArbeit.git@main"
        """,
    ),
    markdown(
        "wheel-intro",
        r"""
        ### 1.1 Geprüftes Minimal-`bpy` auswählen

        Das inoffizielle Export-Wheel enthält nur den geprüften Vertrag für
        Meshes, Materialien, Collections, Hierarchien, Text-Datenblöcke und das
        Speichern von `.blend`-Dateien. Rendering, Simulation, Audio/Video,
        Blender-Oberfläche und fremde Dateiformate gehören nicht zum Umfang.

        Die passende Datei wird anhand der Python-Version gewählt und vor der
        Installation mit SHA-256 geprüft. Der Download beträgt rund **31,3 MB**.
        """,
    ),
    code(
        "select-wheel",
        """
        import hashlib
        import platform
        import sys
        import sysconfig
        from pathlib import Path
        from urllib.request import urlretrieve

        assert sys.platform.startswith("linux"), f"Nur Linux wird unterstützt: {sys.platform}"
        assert platform.machine() in {"x86_64", "AMD64"}, platform.machine()
        libc_name, libc_version = platform.libc_ver()
        assert libc_name == "glibc", (libc_name, libc_version)
        assert tuple(map(int, libc_version.split(".")[:2])) >= (2, 28), libc_version

        python_key = f"{sys.version_info.major}.{sys.version_info.minor}"
        soabi = sysconfig.get_config_var("SOABI")
        assert soabi and soabi.startswith(
            f"cpython-{sys.version_info.major}{sys.version_info.minor}"
        ), soabi

        wheel_names = {
            "3.11": "bpy-4.5.3+mesh1-cp311-cp311-manylinux_2_28_x86_64.whl",
            "3.12": "bpy-4.5.3+mesh1-cp312-cp312-manylinux_2_28_x86_64.whl",
        }
        wheel_hashes = {
            "3.11": "651c74dce5c00b1a822c4ff0d78d6d0cf3904079a78308e171acf28e53629409",
            "3.12": "1f26833ce95fd2c60f42d9f44b34a97326a3a6246d0b3d177d59fb83e99e2ff5",
        }
        if python_key not in wheel_names:
            raise RuntimeError(
                f"Kein geprüftes Wheel für Python {python_key}; "
                f"verfügbar: {sorted(wheel_names)}"
            )

        wheel_name = wheel_names[python_key]
        wheel_url = (
            "https://github.com/Hadron-JLeo/BachelorArbeit/releases/download/"
            f"bpy-mesh-4.5.3.1/{wheel_name}"
        )
        wheel_path = Path("/tmp") / wheel_name
        urlretrieve(wheel_url, wheel_path)
        actual_hash = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
        assert actual_hash == wheel_hashes[python_key], (
            actual_hash,
            wheel_hashes[python_key],
        )
        print(
            f"Geprüft: {wheel_path.name} "
            f"({wheel_path.stat().st_size / 1_000_000:.1f} MB)"
        )
        """,
    ),
    code(
        "install-wheel",
        """
        %pip install --no-cache-dir --no-deps --force-reinstall {wheel_path}
        """,
    ),
    markdown(
        "restart-note",
        """
        Falls in dieser Sitzung vorher bereits eine andere `bpy`-Version
        importiert wurde, muss der Kernel jetzt einmal neu gestartet und das
        Notebook erneut von oben ausgeführt werden. In einer frischen Sitzung ist
        kein Neustart nötig.
        """,
    ),
    code(
        "imports",
        """
        from importlib.metadata import version
        import json
        from numbers import Integral

        import bpy
        from mathutils import Quaternion, Vector
        import numpy as np

        from imports import (
            GeometryConfig,
            Polygon3D,
            VisualizationConfig,
            generate_hypercube_surface,
        )
        from imports.visualization import (
            create_open3d_model,
            print_vertex_coordinates,
            show_open3d_model,
        )

        assert version("hypercube-graph-surface") == "0.1.0"
        assert version("bpy") == "4.5.3+mesh1"
        assert bpy.app.background
        print(f"Projektmodule: {version('hypercube-graph-surface')}")
        print(f"Minimal-bpy: {version('bpy')} / Blender {bpy.app.version_string}")
        """,
    ),
    markdown(
        "configuration",
        r"""
        ## 2. Konfiguration

        `shear_margin` erhöht den Scherungsfaktor über die berechnete untere
        Schranke. `cut_fraction` und `cut_margin` legen die vertikale Schnittebene
        fest. `zero_tolerance` dient ausschließlich der Fehlerbehandlung numerisch
        kritischer Operationen; sie rundet keine beliebigen Koordinaten auf null.
        Die Höhe wird auf `target_height` normiert. Die zweite Konfiguration
        steuert nur die interaktive Darstellung.
        """,
    ),
    code(
        "configuration-values",
        """
        geometry_config = GeometryConfig(
            shear_margin=1.0,
            cut_fraction=0.92,  # Im Original als KI-unterstützte Wahl gekennzeichnet.
            cut_margin=0.05,
            zero_tolerance=1e-12,
            target_height=1.0,
        )
        visualization_config = VisualizationConfig(
            model_color="rgb(45, 105, 210)",
            edge_color=(0.08, 0.08, 0.08),
            width=1000,
            height=700,
            opacity=0.30,
        )
        """,
    ),
    markdown(
        "model-and-base",
        r"""
        ## 3. Datenmodell und Basisfall

        Ein `Polygon3D` speichert seine zyklisch geordneten Ecken in einem
        NumPy-Array der Form $(n,3)$. Insbesondere die letzten beiden Ecken haben
        eine feste Bedeutung für den nächsten Schnitt. Die Reihenfolge darf
        deshalb nicht beliebig geändert werden. Die Klasse prüft Form und
        Endlichkeit der Eingabe.

        Der Basisfall $Q_0$ besteht aus dem Einheitsquadrat. Die
        Polygonbezeichnungen werden innerhalb jeder erzeugten Oberfläche vergeben;
        ein global wachsender Objektzähler ist nicht erforderlich.
        """,
    ),
    markdown(
        "geometry-overview",
        r"""
        ## 4. Geometrische Schritte

        Zu Beginn und am Ende jedes Induktionsschritts passt die Projektion in das
        Einheitsquadrat. Die ersten beiden Ecken liegen bei $(0,0)$ und $(0,1)$,
        die letzte bei $(1,0)$. Die letzten beiden Ecken liegen auf $x=1$, alle
        übrigen links davon; die zweite und dritte Ecke liegen auf $y=1$.

        Die Schnittfunktionen in `geometry.py` nutzen diese besondere
        Eckenreihenfolge und sind keine allgemeinen Polygon-Clipping-Verfahren.

        ### 4.1 Schnittpunkt einer Strecke mit einer Ebene

        Für die affine Ebenenfunktion $f$ und die Strecke $p+t(q-p)$ liefert das
        Auflösen von $f(p+t(q-p))=0$ die Formel

        $$t=\frac{f(p)}{f(p)-f(q)},\qquad s=p+t(q-p).$$

        Die Implementierung meldet einen Fehler, wenn kein eindeutig bestimmter
        Schnitt innerhalb der Strecke vorliegt. Die aufrufenden Funktionen prüfen
        zusätzlich die für ihren Schritt vorgesehenen Vorzeichen.

        ### 4.2 Scherung und Höhenverschiebung

        Die Scherung $(x,y,z)\mapsto(x,y,z-sx)$ verändert nur die Höhe. Für
        Zielpunkte $t$ und übrige Punkte $o$ muss
        $s>(z_t-z_o)/(x_t-x_o)$ gelten. Mit dem kleinsten tatsächlichen Ziel-$x$
        wird eine konservative Schranke berechnet. Danach verschiebt die
        Implementierung die Mitte der entstandenen Höhenlücke auf $z=0$.

        ### 4.3 Horizontalschnitt und Spiegelung

        Der Schnitt mit $z=0$ ersetzt die letzten beiden Ecken durch zwei
        Schnittpunkte. Die dadurch erzeugte Seite verbindet jedes Polygon mit
        seiner gespiegelten Kopie. Die Spiegelung verdoppelt die Polygonanzahl.

        ### 4.4 Vertikaler Eckenschnitt

        Die Ebene $x=ay+b$ soll ausschließlich die letzte Ecke entfernen. Dazu
        ist $f(x,y,z)=x-ay-b$ dort positiv und an allen anderen Ecken negativ. Der
        Schnitt ersetzt eine Ecke durch zwei neue und erhöht die Seitenzahl um
        eins. Die ergänzten Prüfungen sichern die Voraussetzungen jedes Laufs ab.

        ### 4.5 Projektive Rückführung und Höhennormierung

        Die verwendete Abbildung lautet

        $$ (x,y,z)\longmapsto\frac{1}{ay+b}\bigl(x,(a+b)y,z\bigr). $$

        Sie bildet die vertikale Schnittebene auf $x'=1$ ab. Der Nenner wird vor
        der Division auf Endlichkeit und strikte Positivität geprüft. Die
        abschließende gemeinsame Skalierung der Höhen erhält die Inzidenzen und
        verbessert die Größenordnung der Koordinaten.
        """,
    ),
    markdown(
        "induction",
        r"""
        ## 5. Induktive Konstruktion

        Aus dem Basisquadrat entsteht durch $d$ Induktionsschritte die Darstellung
        von $Q_d$. Jeder Schritt verdoppelt die Polygonanzahl und erhöht die
        Eckenzahl um eins. `generate_hypercube_surface` ruft dafür die Operationen
        aus `geometry.py` in der festgelegten Reihenfolge auf.

        Das Beispiel verwendet $d=4$. Erwartet werden 16 Polygone mit jeweils
        8 Ecken und $4\cdot2^3=32$ Graphkanten.
        """,
    ),
    code(
        "construct-surface",
        """
        dimension = 4
        surface = generate_hypercube_surface(dimension, config=geometry_config)

        expected_polygons = 2 ** dimension
        expected_vertices_per_polygon = dimension + 4
        expected_graph_edges = 0 if dimension == 0 else dimension * 2 ** (dimension - 1)

        assert len(surface) == expected_polygons
        assert all(
            len(polygon.vertices) == expected_vertices_per_polygon
            for polygon in surface
        )
        assert all(np.isfinite(polygon.vertices).all() for polygon in surface)

        print(f"Dimension: Q_{dimension}")
        print(f"Polygone: {len(surface)}")
        print(f"Ecken je Polygon: {len(surface[0].vertices)}")
        print(f"Graphkanten (kombinatorisch): {expected_graph_edges}")
        """,
    ),
    markdown(
        "visualization",
        r"""
        ## 6. Interaktive Darstellung

        Jedes konvexe Polygon wird für Open3D in einen Dreiecksfächer zerlegt. Die
        Diagonalen dienen nur der Darstellung und sind keine Graphkanten. Das
        Linienmodell zeigt die ursprünglichen Polygonseiten. Eine gemeinsame Seite
        wird von beiden Polygonen gespeichert und deshalb doppelt gezeichnet.

        Plotly zeigt das Modell interaktiv im Notebook. Die Transparenz erleichtert
        den Blick auf verdeckte Teile, kann aber die räumliche Wahrnehmung
        beeinflussen. Der Blender-Export verwendet später wieder die originalen
        n-Ecke und nicht diese Dreiecksfächer.
        """,
    ),
    code(
        "show-surface",
        """
        mesh, edges = create_open3d_model(surface, config=visualization_config)
        figure = show_open3d_model(
            mesh,
            edges,
            title=f"Polygonfamilie mit Adjazenzgraph Q_{dimension}",
            config=visualization_config,
        )
        """,
    ),
    markdown(
        "coordinates",
        r"""
        ### 6.1 Eckpunkte mit Labels und Koordinaten

        Jede Zeile enthält das Polygonlabel, ein eindeutiges Eckpunktlabel und die
        NumPy-Koordinaten. Gemeinsame geometrische Eckpunkte werden je zugehörigem
        Polygon separat ausgegeben. Für $Q_4$ entstehen $16\cdot8=128$ Einträge.
        Bis zu 17 signifikante Stellen geben die gespeicherten
        `float64`-Koordinaten wieder.
        """,
    ),
    code(
        "print-coordinates",
        """
        print_vertex_coordinates(surface, precision=17)
        """,
    ),
    markdown(
        "export-intro",
        r"""
        ## 7. Direkter Export mit Minimal-`bpy`

        Der Export läuft **im Notebook-Kernel**. Er startet keinen Blender-Prozess
        und lädt keine vollständige Blender-Anwendung. Jede `Polygon3D`-Instanz
        wird zu einem eigenen Mesh-Objekt mit genau einer n-eckigen Fläche. Die
        Eckenreihenfolge, Koordinatenachsen und der Maßstab bleiben erhalten.

        Empties bilden eine Hierarchie der Induktionsschritte. Im nullbasierten
        Listenindex beschreibt das niederwertigste Bit den ersten Schritt; für die
        Gruppierung werden die Bits deshalb umgekehrt gelesen. `0` bedeutet
        Originalzweig, `1` Spiegelzweig. Die Gruppen beschreiben die Entstehung der
        Polygone, nicht die Adjazenz. Die $Q_d$-Nachbarn stehen zusätzlich als
        NumPy-Indizes in `neighbor_indices_json`.

        ```text
        Q4_Modell                         Collection
        └── Q4_Gesamtmodell               Empty: gesamtes Modell bewegen
            ├── Schritt_01_0
            │   ├── Schritt_02_00
            │   │   ├── Schritt_03_000
            │   │   │   ├── Polygon_0000 (poly_1)
            │   │   │   └── Polygon_0001 (poly_9)
            │   │   └── Schritt_03_001 …
            │   └── Schritt_02_01 …
            └── Schritt_01_1 …
        ```

        Die unveränderten `float64`-Quelldaten werden als JSON-Begleitdatei und im
        Blender-Textblock `NumPy_Quelldaten.json` gespeichert. Die Meshkoordinaten
        selbst verwenden Blenders Koordinatenpräzision.
        """,
    ),
    code(
        "export-functions",
        r'''
        import colorsys


        def surface_payload(polygons: list[Polygon3D], dimension: int) -> dict:
            """Serialisiert die Generatorreihenfolge samt Hyperwürfel-Nachbarn."""
            if isinstance(dimension, (bool, np.bool_)) or not isinstance(
                dimension, Integral
            ):
                raise TypeError("dimension muss eine ganze Zahl sein.")
            dimension = int(dimension)
            if dimension < 0 or len(polygons) != 2 ** dimension:
                raise ValueError(
                    "Die Polygonzahl muss 2**dimension mit dimension >= 0 sein."
                )
            if any(len(polygon.vertices) != dimension + 4 for polygon in polygons):
                raise ValueError("Jedes Polygon muss dimension + 4 Ecken besitzen.")

            records = []
            for index, polygon in enumerate(polygons):
                graph_bits = format(index, f"0{dimension}b") if dimension else ""
                records.append(
                    {
                        "index": index,
                        "label": polygon.label,
                        "graph_bits": graph_bits,
                        "construction_path": graph_bits[::-1],
                        "neighbor_indices": [
                            index ^ (1 << bit) for bit in range(dimension)
                        ],
                        "vertices": np.asarray(
                            polygon.vertices, dtype=float
                        ).tolist(),
                    }
                )
            return {
                "schema_version": 2,
                "dimension": dimension,
                "coordinate_system": (
                    "NumPy x/y/z unverändert, keine Achsendrehung oder Skalierung"
                ),
                "hierarchy": (
                    "chronologischer Induktionspfad; 0=Original, 1=Spiegelbild"
                ),
                "polygons": records,
            }


        def build_blender_scene(data: dict) -> dict:
            """Erzeugt die vollständige Blender-Szene im aktiven Python-Prozess."""
            if not bpy.app.background:
                raise RuntimeError("Dieses Minimal-bpy ist nur für Headless-Export gedacht.")

            bpy.ops.wm.read_factory_settings(use_empty=True)
            scene = bpy.context.scene
            dimension = int(data["dimension"])
            records = data["polygons"]
            scene.name = f"Q{dimension}_Polygonfamilie"

            model_collection = bpy.data.collections.new(f"Q{dimension}_Modell")
            scene.collection.children.link(model_collection)
            points = [
                Vector(vertex)
                for record in records
                for vertex in record["vertices"]
            ]
            lower = Vector(
                tuple(min(point[axis] for point in points) for axis in range(3))
            )
            upper = Vector(
                tuple(max(point[axis] for point in points) for axis in range(3))
            )
            center = (lower + upper) / 2
            extent = max((upper - lower).length, 1.0)

            def empty(name: str, parent=None):
                obj = bpy.data.objects.new(name, None)
                model_collection.objects.link(obj)
                obj.empty_display_type = "PLAIN_AXES"
                obj.empty_display_size = extent * 0.04
                obj.parent = parent
                return obj

            root = empty(f"Q{dimension}_Gesamtmodell")
            root.location = center
            root["role"] = "model_root"
            root["dimension"] = dimension
            root["polygon_count"] = len(records)
            root["hierarchy"] = (
                "Induktionspfad: links zuerst Schritt 1; "
                "0=Original, 1=Spiegelbild"
            )

            groups = {"": root}
            materials = []
            for index in range(8):
                rgb = colorsys.hsv_to_rgb(index / 8, 0.48, 0.72)
                material = bpy.data.materials.new(f"Polygonfarbe_{index + 1:02d}")
                material.diffuse_color = (*rgb, 1.0)
                material.use_nodes = True
                shader = material.node_tree.nodes.get("Principled BSDF")
                shader.inputs["Base Color"].default_value = (*rgb, 1.0)
                shader.inputs["Roughness"].default_value = 0.65
                materials.append(material)

            polygon_objects = []
            for record in records:
                path = record["construction_path"]
                for depth in range(1, len(path)):
                    prefix = path[:depth]
                    if prefix not in groups:
                        group = empty(
                            f"Schritt_{depth:02d}_{prefix}",
                            groups[prefix[:-1]],
                        )
                        group["role"] = "construction_group"
                        group["construction_path"] = prefix
                        group["step"] = depth
                        groups[prefix] = group

                vertices = record["vertices"]
                origin_xyz = tuple(
                    sum(vertex[axis] for vertex in vertices) / len(vertices)
                    for axis in range(3)
                )
                origin = Vector(origin_xyz)
                local_vertices = [
                    tuple(vertex[axis] - origin_xyz[axis] for axis in range(3))
                    for vertex in vertices
                ]
                name = f"Polygon_{path or 'Basis'}"
                mesh = bpy.data.meshes.new(name + "_Mesh")
                mesh.from_pydata(
                    local_vertices,
                    [],
                    [list(range(len(vertices)))],
                )
                mesh.update()

                obj = bpy.data.objects.new(name, mesh)
                model_collection.objects.link(obj)
                obj.parent = groups.get(path[:-1], root)
                obj.location = origin - center
                obj["role"] = "source_polygon"
                obj["source_index"] = record["index"]
                obj["source_label"] = record["label"]
                obj["construction_path"] = path
                obj["graph_bits"] = record["graph_bits"]
                obj["vertex_count_numpy"] = len(vertices)
                obj["neighbor_indices_json"] = json.dumps(
                    record["neighbor_indices"]
                )
                color_index = int((path[:3] or "0").ljust(3, "0"), 2)
                obj.data.materials.append(materials[color_index])
                obj.color = materials[color_index].diffuse_color
                obj.show_wire = True
                obj.show_all_edges = True
                polygon_objects.append(obj)

            bpy.context.view_layer.update()
            source_text = bpy.data.texts.new("NumPy_Quelldaten.json")
            source_text.write(
                json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
            )
            readme = bpy.data.texts.new("LIESMICH_Blender")
            readme.write(
                "Gesamtmodell: Q*_Gesamtmodell auswählen und G/R/S verwenden.\n"
                "Schritt-Gruppen bewegen ihre Polygon-Nachkommen.\n"
                "Einzelne Polygone sind eigenständige Mesh-Objekte.\n"
                "Tab wechselt für ein Polygon in den Bearbeitungsmodus.\n"
                "0=Original und 1=Spiegelbild im chronologischen Induktionspfad.\n"
                "Die Hierarchie ist kein Adjazenzbaum.\n"
                "Nachbarn stehen in neighbor_indices_json.\n"
                "Die Text-Quelldaten enthalten die float64-Koordinaten.\n"
                "Punkte wurden nicht verschmolzen; die Familie hat freie Ränder.\n"
                "Für den Blick ins Innere: X-Ray oder Drahtgitter verwenden.\n"
            )

            for screen in bpy.data.screens:
                for area in screen.areas:
                    if area.type == "VIEW_3D":
                        space = area.spaces.active
                        space.shading.type = "SOLID"
                        space.shading.color_type = "MATERIAL"
                        space.shading.show_cavity = True
                        space.region_3d.view_location = center
                        space.region_3d.view_distance = extent * 1.65
                        space.region_3d.view_rotation = Quaternion(
                            (0.820, 0.425, 0.176, 0.340)
                        ).normalized()
                        space.clip_start = 0.0001
                        space.clip_end = extent * 100

            bpy.context.view_layer.objects.active = root
            root.select_set(True)
            return {
                "blender_version": bpy.app.version_string,
                "dimension": dimension,
                "mesh_objects": len(polygon_objects),
                "mesh_faces": sum(
                    len(obj.data.polygons) for obj in polygon_objects
                ),
                "mesh_vertices": sum(
                    len(obj.data.vertices) for obj in polygon_objects
                ),
                "empty_objects": len(groups),
            }


        def export_surface_to_blend(
            polygons: list[Polygon3D],
            dimension: int,
            filepath: str | Path,
            *,
            overwrite: bool = False,
        ) -> dict:
            """Speichert Oberfläche, Metadaten und Hierarchie direkt als .blend."""
            path = Path(filepath).expanduser().resolve()
            if path.suffix.lower() != ".blend":
                raise ValueError("Der Zielpfad muss auf .blend enden.")
            if path.exists() and not overwrite:
                raise FileExistsError(path)

            data = surface_payload(polygons, dimension)
            path.parent.mkdir(parents=True, exist_ok=True)
            json_path = path.with_suffix(".json")
            json_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False),
                encoding="utf-8",
            )

            result = build_blender_scene(data)
            bpy.context.preferences.filepaths.save_version = 0
            save_result = bpy.ops.wm.save_as_mainfile(
                filepath=str(path),
                check_existing=False,
                compress=True,
            )
            if save_result != {"FINISHED"} or not path.is_file():
                raise RuntimeError(f"Die .blend-Datei wurde nicht geschrieben: {path}")
            return {
                **result,
                "blend_path": str(path),
                "json_path": str(json_path),
                "blend_bytes": path.stat().st_size,
            }
        ''',
    ),
    markdown(
        "export-execution-intro",
        """
        ### 7.1 Aktuelle Oberfläche speichern

        Die nächste Zelle exportiert genau die aktuelle Liste `surface`. Bei einer
        Wiederholung werden nur die gleichnamigen erzeugten Dateien ersetzt. Eine
        manuell in Blender bearbeitete Fassung sollte deshalb unter einem anderen
        Namen gespeichert werden.
        """,
    ),
    code(
        "export-execution",
        """
        export_directory = Path.cwd() / "blender_export"
        blend_path = export_directory / f"Q{dimension}_Hypercube_Polygonfamilie.blend"

        blender_export = export_surface_to_blend(
            surface,
            dimension,
            blend_path,
            overwrite=True,
        )

        assert blender_export["mesh_objects"] == 2 ** dimension
        assert blender_export["mesh_faces"] == 2 ** dimension
        assert blender_export["mesh_vertices"] == (
            2 ** dimension * (dimension + 4)
        )
        assert blender_export["empty_objects"] == 2 ** dimension - 1

        print(f"Blender-Datei: {blender_export['blend_path']}")
        print(f"Quelldaten: {blender_export['json_path']}")
        print(f"Blender-Version: {blender_export['blender_version']}")
        print(
            "Mesh-Objekte / Flächen / Ecken: "
            f"{blender_export['mesh_objects']} / "
            f"{blender_export['mesh_faces']} / "
            f"{blender_export['mesh_vertices']}"
        )
        print(f"Elternobjekte: {blender_export['empty_objects']}")
        print(f"Dateigröße: {blender_export['blend_bytes'] / 1_000_000:.2f} MB")
        """,
    ),
    markdown(
        "download-intro",
        """
        ### 7.2 `.blend`-Datei herunterladen

        In Google Colab startet die nächste Zelle den Browser-Download. In einem
        lokalen Jupyter-System zeigt sie stattdessen einen anklickbaren Dateilink.
        """,
    ),
    code(
        "download-blend",
        """
        try:
            from google.colab import files

            files.download(str(blend_path))
        except ImportError:
            from IPython.display import FileLink, display

            display(FileLink(str(blend_path)))
        """,
    ),
    markdown(
        "using-blend",
        r"""
        ### 7.3 Die Datei in Blender verwenden

        1. Die heruntergeladene `.blend`-Datei über **File → Open** öffnen.
        2. Im Outliner `Q4_Gesamtmodell` auswählen, um mit **G**, **R** oder **S**
           die gesamte Familie zu bewegen, zu drehen oder zu skalieren.
        3. Ein `Polygon_…` auswählen. **Tab** öffnet den Bearbeitungsmodus mit den
           ursprünglichen Polygonecken und genau einer n-eckigen Fläche.
        4. **Alt+Z** aktiviert X-Ray; **Z → Wireframe** zeigt das Drahtgitter.
           Im Text Editor stehen `LIESMICH_Blender` und
           `NumPy_Quelldaten.json`.

        Die Polygone bleiben getrennte Objekte. Gemeinsame Seiten sind
        geometrisch deckungsgleich, ihre Eckpunkte werden jedoch nicht
        verschmolzen. Die Polygonfamilie besitzt freie Ränder und ist kein
        geschlossener Volumenkörper.
        """,
    ),
    markdown(
        "limits-and-sources",
        r"""
        ## 8. Einordnung, Grenzen und Herkunft

        Die Datenmenge wächst mit $2^d(d+4)$ gespeicherten Ecken. Große
        Dimensionen müssen hinsichtlich Laufzeit, Speicher und numerischer
        Abstände gesondert untersucht werden. Erfolgreiche Läufe in kleinen
        Dimensionen begründen keine unbeschränkte Zuverlässigkeit der
        Gleitkommaimplementierung.

        Das Minimal-`bpy` ist ein inoffizieller, eingeschränkter Export-Build aus
        dem Blender-4.5.3-Quellstand. Es ersetzt Blender nicht allgemein. Die
        unterstützte Funktionalität und die reproduzierbaren Build-Nachweise sind
        im Repository unter `bpy_minimal/` dokumentiert. Das Wheel wurde unter
        CPython 3.11 und 3.12 unter anderem für n-Ecke, Materialien, Hierarchien,
        Textblöcke, komprimierte Dateien und die wechselseitige Lesbarkeit mit dem
        offiziellen Blender 4.5.3 geprüft.

        **Einsatz generativer KI.** Im Ausgangsnotebook waren Teile der
        Parameterwahl und Visualisierung als KI-unterstützt gekennzeichnet. Diese
        Hinweise bleiben erhalten. Die Modularisierung, die Erläuterungen und der
        direkte Export wurden mit generativer KI überarbeitet und technisch
        geprüft. Die algebraischen Erläuterungen beschreiben die Implementierung
        und beanspruchen keine ungeprüfte eigenständige wissenschaftliche
        Urheberschaft.

        **Literatur und Dokumentation**

        - E. Arseneva et al.: *Adjacency Graphs of Polyhedral Surfaces*. Discrete
          & Computational Geometry **71**, 1429–1455 (2024), Abschnitt 3.4,
          Proposition 3.14. [DOI und Volltext](https://doi.org/10.1007/s00454-023-00537-6).
        - McMullen, Schulz und Wills (1983) werden dort als Ursprung der
          Konstruktion genannt.
        - [Open3D 0.19: Plotly-Darstellung](https://www.open3d.org/docs/release/python_api/open3d.visualization.draw_plotly.html)
        - [Plotly: Renderer](https://plotly.com/python/renderers/)
        - [Blender Python API: Mesh.from_pydata](https://docs.blender.org/api/4.5/bpy.types.Mesh.html#bpy.types.Mesh.from_pydata)
        - [Blender Python API: Datei speichern](https://docs.blender.org/api/4.5/bpy.ops.wm.html#bpy.ops.wm.save_as_mainfile)
        """,
    ),
]


notebook = {
    "cells": cells,
    "metadata": {
        "colab": {"provenance": []},
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.12",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

OUTPUT.write_text(
    json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
    encoding="utf-8",
)
print(OUTPUT)
