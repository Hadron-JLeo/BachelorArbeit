"""Erzeugt runde, verbundene Kanten als renderbares Blender-Mesh.

Im Blender-Texteditor ausführen oder mit:
    blender input.blend --background --python blender_edges_to_mesh.py

Gemeinsame Endpunkte bekommen runde Übergänge, freie Enden runde Kappen.
Voxel-Remeshing verschmilzt die Rundprofile und Übergänge zu einer Oberfläche.
Getrennte Kantengruppen bleiben erhalten. Auch räumlich überlappende Profile
verschmelzen: EDGE_RADIUS daher kleiner als die halbe freie Distanz wählen,
wenn benachbarte Kanten getrennt bleiben sollen (mit etwas Reserve).

Die Quellobjekte bleiben unverändert. Das Ergebnis ist Darstellungsgeometrie;
für geometrische Prüfungen weiterhin die ursprünglichen Polygone verwenden.
Die Blender-Datei bei Bedarf anschließend selbst speichern.
"""

import math

import bpy
from mathutils import Vector


# ------------------------------- Einstellungen ---------------------------

SOURCE_MODE = "ALL_MESH_OBJECTS"  # Alternativ: "SELECTED"
OUTPUT_OBJECT_NAME = "EdgeMesh"
OUTPUT_COLLECTION_NAME = "EdgeMesh_Output"

EDGE_RADIUS = 0.03              # Dicke der sichtbaren Kanten in Blender-Einheiten
SIDES = 32                      # Kreisauflösung; vorher 6
JOINT_RINGS = 16                 # Auflösung der runden Enden und Verbindungen
VOXELS_PER_RADIUS = 6            # 4 = schneller, 6 = fein, 8 = noch feiner
SMOOTH_ITERATIONS = 3            # Leichte Glättung nach dem Verschmelzen
SMOOTH_FACTOR = 0.4
ONLY_BOUNDARY_EDGES = False
DELETE_OLD_OUTPUT = True

MATERIAL_NAME = "EdgeMesh_Material"
MATERIAL_COLOR = (0.03, 0.18, 0.8, 1.0)
MATERIAL_ROUGHNESS = 0.35

OUTPUT_TAG = "_edge_mesh_output"
COORDINATE_DECIMALS = 7


def coordinate_key(point):
    """Fasst bis auf kleine Rundungsfehler gleiche Koordinaten zusammen."""
    return tuple(round(value, COORDINATE_DECIMALS) for value in point)


def is_output_object(obj):
    """Erkennt auch Ausgaben der bisherigen Skriptversion."""
    return (
        bool(obj.get(OUTPUT_TAG, False))
        or obj.name == OUTPUT_OBJECT_NAME
        or any(c.name == OUTPUT_COLLECTION_NAME for c in obj.users_collection)
    )


def get_source_objects():
    """Liefert Quell-Meshes, ohne bereits erzeugte Kanten erneut zu verarbeiten."""
    objects = (bpy.context.selected_objects if SOURCE_MODE == "SELECTED"
               else bpy.context.scene.objects)
    return [obj for obj in objects
            if obj.type == "MESH" and not is_output_object(obj)]


def get_output_collection():
    collection = bpy.data.collections.get(OUTPUT_COLLECTION_NAME)
    if collection is None:
        collection = bpy.data.collections.new(OUTPUT_COLLECTION_NAME)
    if collection not in tuple(bpy.context.scene.collection.children_recursive):
        bpy.context.scene.collection.children.link(collection)
    return collection


def remove_mesh_object(obj):
    mesh = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if isinstance(mesh, bpy.types.Mesh) and mesh.users == 0:
        bpy.data.meshes.remove(mesh)


def collect_edges(objects, depsgraph):
    """Extrahiert eindeutige Kanten nach Anwendung der Quell-Modifikatoren."""
    edges = {}
    points = {}
    for obj in objects:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        if mesh is None:
            continue
        try:
            world_matrix = evaluated.matrix_world
            edge_use_count = {}
            if ONLY_BOUNDARY_EDGES:
                for polygon in mesh.polygons:
                    for a, b in polygon.edge_keys:
                        key = tuple(sorted((a, b)))
                        edge_use_count[key] = edge_use_count.get(key, 0) + 1

            for edge in mesh.edges:
                a, b = edge.vertices
                if ONLY_BOUNDARY_EDGES:
                    uses = edge_use_count.get(tuple(sorted((a, b))), 0)
                    if uses not in (0, 1):
                        continue

                start = world_matrix @ mesh.vertices[a].co
                end = world_matrix @ mesh.vertices[b].co
                key_a = coordinate_key(start)
                key_b = coordinate_key(end)
                if key_a == key_b or (end - start).length <= 1e-8:
                    continue

                # Rundprofile und Verbindungskugeln nutzen dieselben Endpunkte.
                start = points.setdefault(key_a, start)
                end = points.setdefault(key_b, end)
                key = tuple(sorted((key_a, key_b)))
                edges.setdefault(key, (start, end))
        finally:
            evaluated.to_mesh_clear()
    return list(edges.values())


def add_cylinder(vertices, faces, start, end, radius, sides):
    """Ergänzt ein geschlossenes Rundprofil mit nach außen gerichteten Flächen."""
    axis = (end - start).normalized()
    reference = Vector((0.0, 0.0, 1.0))
    if abs(axis.dot(reference)) > 0.9:
        reference = Vector((0.0, 1.0, 0.0))
    side_a = axis.cross(reference).normalized()
    side_b = axis.cross(side_a).normalized()
    base_index = len(vertices)

    for point in (start, end):
        for i in range(sides):
            angle = 2.0 * math.pi * i / sides
            offset = radius * (math.cos(angle) * side_a
                               + math.sin(angle) * side_b)
            vertices.append(tuple(point + offset))

    # Die Kappen liegen später innerhalb der runden Verbindungen.
    faces.append(tuple(base_index + i for i in reversed(range(sides))))
    faces.append(tuple(base_index + sides + i for i in range(sides)))
    for i in range(sides):
        j = (i + 1) % sides
        faces.append((base_index + i, base_index + j,
                      base_index + sides + j, base_index + sides + i))


def add_sphere(vertices, faces, center, radius, sides, rings):
    """Ergänzt eine Verbindungskugel ohne doppelte Pol-Eckpunkte."""
    north = len(vertices)
    vertices.append(tuple(center + Vector((0.0, 0.0, radius))))
    first_ring = len(vertices)

    for ring in range(1, rings):
        latitude = math.pi * ring / rings
        ring_radius = radius * math.sin(latitude)
        z = radius * math.cos(latitude)
        for i in range(sides):
            angle = 2.0 * math.pi * i / sides
            vertices.append(tuple(center + Vector((
                ring_radius * math.cos(angle),
                ring_radius * math.sin(angle), z))))

    south = len(vertices)
    vertices.append(tuple(center - Vector((0.0, 0.0, radius))))
    last_ring = first_ring + (rings - 2) * sides

    for i in range(sides):
        j = (i + 1) % sides
        faces.append((north, first_ring + i, first_ring + j))
        faces.append((last_ring + i, south, last_ring + j))
    for ring in range(rings - 2):
        upper = first_ring + ring * sides
        lower = upper + sides
        for i in range(sides):
            j = (i + 1) % sides
            faces.append((upper + i, lower + i, lower + j, upper + j))


def make_material():
    material = bpy.data.materials.get(MATERIAL_NAME)
    if material is None:
        material = bpy.data.materials.new(MATERIAL_NAME)
    material.diffuse_color = MATERIAL_COLOR
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled is not None:
        principled.inputs["Base Color"].default_value = MATERIAL_COLOR
        principled.inputs["Roughness"].default_value = MATERIAL_ROUGHNESS
    return material


def fuse_and_smooth(output):
    """Verschmilzt überlappende Volumen und übernimmt das Ergebnis als Mesh."""
    remesh = output.modifiers.new("Verbindungen verschmelzen", "REMESH")
    remesh.mode = "VOXEL"
    remesh.voxel_size = EDGE_RADIUS / VOXELS_PER_RADIUS
    remesh.adaptivity = 0.0
    remesh.use_smooth_shade = True
    remesh.use_remove_disconnected = False

    if SMOOTH_ITERATIONS:
        smooth = output.modifiers.new("Oberfläche glätten", "SMOOTH")
        smooth.factor = SMOOTH_FACTOR
        smooth.iterations = SMOOTH_ITERATIONS

    # Auswertung ohne kontextabhängige bpy.ops-Aufrufe, auch im Hintergrund.
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = output.evaluated_get(depsgraph)
    fused_mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=depsgraph)
    if not fused_mesh.polygons:
        bpy.data.meshes.remove(fused_mesh)
        raise RuntimeError("Remeshing hat keine Oberfläche erzeugt.")

    old_mesh = output.data
    output.modifiers.clear()
    output.data = fused_mesh
    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    fused_mesh.name = OUTPUT_OBJECT_NAME + "_Data"
    for polygon in fused_mesh.polygons:
        polygon.use_smooth = True
    fused_mesh.update()


def build_edge_mesh(edge_pairs):
    vertices, faces = [], []
    joints = {}
    for start, end in edge_pairs:
        add_cylinder(vertices, faces, start, end, EDGE_RADIUS, SIDES)
        joints.setdefault(coordinate_key(start), start)
        joints.setdefault(coordinate_key(end), end)
    for point in joints.values():
        add_sphere(vertices, faces, point, EDGE_RADIUS, SIDES, JOINT_RINGS)

    mesh = bpy.data.meshes.new(OUTPUT_OBJECT_NAME + "_Data")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    output = bpy.data.objects.new(OUTPUT_OBJECT_NAME, mesh)
    output[OUTPUT_TAG] = True
    try:
        get_output_collection().objects.link(output)
        fuse_and_smooth(output)
        output.data.materials.clear()
        output.data.materials.append(make_material())
    except Exception:
        remove_mesh_object(output)
        raise
    return output


def validate_settings():
    if SOURCE_MODE not in {"ALL_MESH_OBJECTS", "SELECTED"}:
        raise ValueError('SOURCE_MODE muss "ALL_MESH_OBJECTS" oder "SELECTED" sein.')
    if not math.isfinite(EDGE_RADIUS) or EDGE_RADIUS <= 0:
        raise ValueError("EDGE_RADIUS muss positiv und endlich sein.")
    if not isinstance(SIDES, int) or SIDES < 8:
        raise ValueError("SIDES muss eine ganze Zahl von mindestens 8 sein.")
    if not isinstance(JOINT_RINGS, int) or JOINT_RINGS < 4:
        raise ValueError("JOINT_RINGS muss eine ganze Zahl von mindestens 4 sein.")
    if not math.isfinite(VOXELS_PER_RADIUS) or VOXELS_PER_RADIUS < 3:
        raise ValueError("VOXELS_PER_RADIUS muss endlich und mindestens 3 sein.")
    if not isinstance(SMOOTH_ITERATIONS, int) or SMOOTH_ITERATIONS < 0:
        raise ValueError("SMOOTH_ITERATIONS muss eine nichtnegative ganze Zahl sein.")
    if not 0 <= SMOOTH_FACTOR <= 1:
        raise ValueError("SMOOTH_FACTOR muss zwischen 0 und 1 liegen.")


def main():
    validate_settings()
    if bpy.context.mode != "OBJECT":
        raise RuntimeError("Bitte vor dem Ausführen in den Object Mode wechseln.")

    source_objects = get_source_objects()
    if not source_objects:
        raise RuntimeError("Keine Quell-Meshes gefunden. Bei SELECTED die "
                           "ursprünglichen Objekte auswählen.")
    edge_pairs = collect_edges(source_objects, bpy.context.evaluated_depsgraph_get())
    if not edge_pairs:
        raise RuntimeError("Die Quell-Meshes enthalten keine verwendbaren Kanten.")

    # Die bisherige Ausgabe erst nach erfolgreichem Neuaufbau ersetzen.
    old_outputs = [obj for obj in bpy.context.scene.objects
                   if obj.type == "MESH" and (
                       obj.get(OUTPUT_TAG, False) or obj.name == OUTPUT_OBJECT_NAME)]
    print(f"Erzeuge Rundprofile für {len(edge_pairs)} Kanten ...", flush=True)
    output = build_edge_mesh(edge_pairs)
    if DELETE_OLD_OUTPUT:
        for obj in old_outputs:
            remove_mesh_object(obj)
        output.name = OUTPUT_OBJECT_NAME
        output.data.name = OUTPUT_OBJECT_NAME + "_Data"

    bpy.context.view_layer.objects.active = output
    output.select_set(True)
    print(f"Erstellt: {output.name}, {len(edge_pairs)} Quellkanten, "
          f"{len(output.data.polygons)} Flächen; Verbindungen verschmolzen.")
    return output


if __name__ == "__main__":
    main()
