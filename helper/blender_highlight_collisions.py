"""Markiert Schnitt- und Kontaktstellen zwischen Blender-Meshes schwarz.

Verwendung: Im Blender-Texteditor öffnen und im Object Mode ausführen.
Danach wie gewohnt rendern. Nach Änderungen an Geometrie, Kamera, Auflösung
oder Frame erneut ausführen. Das Skript speichert die .blend-Datei nicht.

Ausgabe in der Collection CollisionHighlights:
  - Schnittlinien mit einheitlicher Breite LINE_WIDTH_PX im Renderbild;
  - punktförmige Berührungen als schwarze Punkte mit demselben Durchmesser;
  - koplanare Überlappungen als schwarze Flächen mit kleinem Abstand.
Die Quellobjekte und ihre Materialien bleiben unverändert.

Gilt für getrennte Mesh-Objekte, auch für offene Polygonflächen. Modifikatoren
und Welttransformationen werden berücksichtigt. Gemeinsame Kanten zählen als
Kontakt, auch wenn sie in einer polyedrischen Konstruktion zulässig sind.
Kein Test auf Selbstschnitte innerhalb eines Objekts oder reine Einschließung
geschlossener Körper ohne Oberflächenkontakt. Nicht realisierte Instanzen und
Kurven sind keine Quell-Meshes.

LINE_WIDTH_MODE="PIXELS" benötigt eine aktive Perspektiv- oder Orthokamera
ohne Tiefenschärfe. Die Linien werden als Kamera-Overlay erzeugt, damit sie
nicht seitlich in den Quellflächen verschwinden. RESPECT_OCCLUSION prüft die
Mittellinie in Abständen von höchstens einem Pixel auf Mesh-Verdeckungen.
Dabei gelten auch transparente Mesh-Flächen als undurchsichtig; Kantenhelfer
werden übersprungen. False zeigt alle Kontakte, auch hinter anderen Objekten.
Keine Berücksichtigung von Volumen, Haaren, Tiefenschärfe oder Bewegungsunschärfe.

EPSILON ist eine numerische Toleranz in Blender-Einheiten, kein physikalischer
Kollisionsabstand. LINE_WIDTH_PX gibt die gesamte Strichbreite in Pixeln der
eingestellten Renderauflösung an. Antialiasing kann Randpixel aufhellen.
LINE_WIDTH_MODE="WORLD" nutzt stattdessen Rundprofile mit LINE_DIAMETER in
Blender-Einheiten; dort können Perspektive und Verdeckung die sichtbare
Breite verändern. In diesem Modus sind Kamera und Auflösung unerheblich.
Das Ergebnis ist eine Darstellungshilfe, kein exakter Beweis
für die Gültigkeit einer mathematischen Konstruktion.
"""

import math
from dataclasses import dataclass
from itertools import combinations

import bpy
import numpy as np
from mathutils import Vector


# ------------------------------- Einstellungen ---------------------------

SOURCE_MODE = "ALL_MESH_OBJECTS"   # Alternativ: "SELECTED"
SKIP_HIDDEN_RENDER = True
IGNORE_EDGE_HELPERS = True       # Kanten-Hilfsmeshes aus dem vorherigen Skript

LINE_WIDTH_MODE = "PIXELS"       # "PIXELS" = gleiche Renderbreite; "WORLD" = 3D-Röhren
LINE_WIDTH_PX = 6.0              # Gemeinsame Breite aller Linien/Punkte im Renderbild
RESPECT_OCCLUSION = True         # False: auch verdeckte Kontakte anzeigen
LINE_DIAMETER = 0.024            # Nur WORLD: gleicher Durchmesser für Linien/Punkte
CURVE_BEVEL_RESOLUTION = 4
MARK_POINT_CONTACTS = True
MARK_COPLANAR_OVERLAPS = True
EPSILON = 1e-6

OUTPUT_COLLECTION_NAME = "CollisionHighlights"
OUTPUT_TAG = "_mesh_collision_highlight"
MATERIAL_NAME = "CollisionHighlights_Black"


# ------------------------------- Geometrie --------------------------------

def unique_points(points, epsilon):
    result = []
    for point in points:
        if not any(np.linalg.norm(point - other) <= epsilon for other in result):
            result.append(np.asarray(point, dtype=np.float64))
    return result


def plane_section(triangle, distances, epsilon):
    """Schneidet ein Dreieck mit einer Ebene über signierte Abstände."""
    points = [triangle[i] for i in range(3) if abs(distances[i]) <= epsilon]
    for i, j in ((0, 1), (1, 2), (2, 0)):
        if ((distances[i] > epsilon and distances[j] < -epsilon)
                or (distances[i] < -epsilon and distances[j] > epsilon)):
            factor = distances[i] / (distances[i] - distances[j])
            points.append(triangle[i] + factor * (triangle[j] - triangle[i]))
    return unique_points(points, epsilon)


def cross_2d(a, b):
    return a[0] * b[1] - a[1] * b[0]


def coplanar_intersection(first, second, normal, epsilon):
    """Schneidet koplanare Dreiecke durch konvexes Polygon-Clipping."""
    axes = [axis for axis in range(3) if axis != int(np.argmax(np.abs(normal)))]
    projected = second[:, axes]
    orientation = 1.0 if cross_2d(projected[1] - projected[0],
                                 projected[2] - projected[0]) >= 0 else -1.0
    polygon = list(first)
    for i in range(3):
        edge_start = projected[i]
        edge = projected[(i + 1) % 3] - edge_start
        edge_length = np.linalg.norm(edge)

        def signed_distance(point):
            return orientation * cross_2d(edge, point[axes] - edge_start) / edge_length

        clipped = []
        if not polygon:
            return None
        previous = polygon[-1]
        previous_distance = signed_distance(previous)
        for current in polygon:
            current_distance = signed_distance(current)
            previous_inside = previous_distance >= -epsilon
            current_inside = current_distance >= -epsilon
            if previous_inside != current_inside:
                factor = previous_distance / (previous_distance - current_distance)
                factor = min(1.0, max(0.0, factor))
                clipped.append(previous + factor * (current - previous))
            if current_inside:
                clipped.append(current)
            previous, previous_distance = current, current_distance
        polygon = unique_points(clipped, epsilon)

    if not polygon:
        return None
    if len(polygon) == 1:
        return "POINT", polygon
    area_vector = np.zeros(3)
    for i in range(1, len(polygon) - 1):
        area_vector += np.cross(polygon[i] - polygon[0], polygon[i + 1] - polygon[0])
    if abs(np.dot(area_vector, normal)) > 2 * epsilon * epsilon:
        return "PATCH", polygon
    start, end = max(combinations(polygon, 2), key=lambda pair: np.linalg.norm(pair[1] - pair[0]))
    if np.linalg.norm(end - start) <= epsilon:
        return "POINT", [(start + end) * 0.5]
    return "SEGMENT", [start, end]


def triangle_intersection(first, second, normal_a, normal_b, epsilon):
    """Liefert None oder einen Kontaktpunkt, ein Segment bzw. ein Polygon."""
    distances_a = (first - second[0]) @ normal_b
    distances_b = (second - first[0]) @ normal_a
    for distances in (distances_a, distances_b):
        if np.all(distances > epsilon) or np.all(distances < -epsilon):
            return None
    if (np.max(np.abs(distances_a)) <= epsilon
            and np.max(np.abs(distances_b)) <= epsilon):
        return coplanar_intersection(first, second, normal_a, epsilon)

    direction = np.cross(normal_a, normal_b)
    length = np.linalg.norm(direction)
    if length <= 1e-12:
        return None
    direction /= length
    section_a = plane_section(first, distances_a, epsilon)
    section_b = plane_section(second, distances_b, epsilon)
    if not section_a or not section_b:
        return None
    origin = section_a[0]
    interval_a = [np.dot(point - origin, direction) for point in section_a]
    interval_b = [np.dot(point - origin, direction) for point in section_b]
    start = max(min(interval_a), min(interval_b))
    end = min(max(interval_a), max(interval_b))
    if start > end + epsilon:
        return None
    if end - start <= epsilon:
        return "POINT", [origin + 0.5 * (start + end) * direction]
    return "SEGMENT", [origin + start * direction, origin + end * direction]


@dataclass
class BoxNode:
    minimum: np.ndarray
    maximum: np.ndarray
    count: int
    indices: object = None
    left: object = None
    right: object = None


def build_box_tree(minima, maxima, indices=None):
    """Hierarchie von Begrenzungsboxen; enthält auch koplanare Kandidaten."""
    if indices is None:
        indices = np.arange(len(minima))
    minimum = minima[indices].min(axis=0)
    maximum = maxima[indices].max(axis=0)
    if len(indices) <= 8:
        return BoxNode(minimum, maximum, len(indices), indices=indices)
    axis = int(np.argmax(maximum - minimum))
    centers = (minima[indices, axis] + maxima[indices, axis]) * 0.5
    ordered = indices[np.argsort(centers, kind="stable")]
    middle = len(ordered) // 2
    return BoxNode(minimum, maximum, len(indices),
                   left=build_box_tree(minima, maxima, ordered[:middle]),
                   right=build_box_tree(minima, maxima, ordered[middle:]))


@dataclass
class MeshSurface:
    name: str
    triangles: np.ndarray
    normals: np.ndarray
    minima: np.ndarray
    maxima: np.ndarray
    tree: BoxNode


def triangle_candidates(first, second, epsilon):
    """Gibt nur Dreieckspaare mit überlappenden Begrenzungsboxen zurück."""
    stack = [(first.tree, second.tree)]
    while stack:
        a, b = stack.pop()
        if np.any(a.maximum < b.minimum - epsilon) or np.any(b.maximum < a.minimum - epsilon):
            continue
        if a.indices is not None and b.indices is not None:
            for i in a.indices:
                mask = (np.all(first.maxima[i] >= second.minima[b.indices] - epsilon, axis=1)
                        & np.all(second.maxima[b.indices] >= first.minima[i] - epsilon, axis=1))
                for j in b.indices[mask]:
                    yield int(i), int(j)
        elif b.indices is not None or (a.indices is None and a.count >= b.count):
            stack.extend(((a.left, b), (a.right, b)))
        else:
            stack.extend(((a, b.left), (a, b.right)))


# ------------------------------- Quellobjekte -----------------------------

def get_source_objects():
    pool = (list(bpy.context.selected_objects) if SOURCE_MODE == "SELECTED"
            else list(bpy.context.view_layer.objects))
    objects = []
    for obj in pool:
        if obj.type != "MESH" or obj.get(OUTPUT_TAG, False):
            continue
        if IGNORE_EDGE_HELPERS and obj.get("_edge_mesh_output", False):
            continue
        if SKIP_HIDDEN_RENDER and obj.hide_render:
            continue
        objects.append(obj)
    if len(objects) < 2:
        available = ", ".join(f"{obj.name} ({obj.type})" for obj in pool[:15]) or "keine"
        raise RuntimeError(
            "Für Schnittstellen werden mindestens zwei getrennte Quell-Meshes benötigt. "
            f"Gefunden: {len(objects)}; SOURCE_MODE={SOURCE_MODE}. "
            "Bei SELECTED beide Originalobjekte auswählen oder ALL_MESH_OBJECTS verwenden. "
            "Ein zusammengefügtes Objekt zählt nur einmal. "
            f"Objekte im Suchbereich: {available}")
    return objects


def read_surface(obj, depsgraph):
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    if mesh is None:
        return None
    try:
        mesh.calc_loop_triangles()
        if not mesh.loop_triangles:
            return None
        coordinates = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
        mesh.vertices.foreach_get("co", coordinates)
        coordinates = coordinates.reshape((-1, 3))
        matrix = np.asarray(evaluated.matrix_world, dtype=np.float64)
        coordinates = coordinates @ matrix[:3, :3].T + matrix[:3, 3]
        indices = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
        mesh.loop_triangles.foreach_get("vertices", indices)
        triangles = coordinates[indices.reshape((-1, 3))]
        normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        areas = np.linalg.norm(normals, axis=1)
        valid = areas > EPSILON * EPSILON
        triangles, normals, areas = triangles[valid], normals[valid], areas[valid]
        if not len(triangles):
            return None
        normals = normals / areas[:, None]
        minima, maxima = triangles.min(axis=1), triangles.max(axis=1)
        return MeshSurface(obj.name, triangles, normals, minima, maxima,
                           build_box_tree(minima, maxima))
    finally:
        evaluated.to_mesh_clear()


class ContactMarks:
    def __init__(self):
        self.segments = {}
        self.points = {}
        self.patches = {}

    def point_key(self, point):
        return tuple(round(float(value) / EPSILON) for value in point)

    def add(self, kind, points, normal):
        if kind == "SEGMENT":
            key = tuple(sorted(self.point_key(point) for point in points))
            self.segments.setdefault(key, points)
        elif kind == "POINT" and MARK_POINT_CONTACTS:
            self.points.setdefault(self.point_key(points[0]), points[0])
        elif kind == "PATCH" and MARK_COPLANAR_OVERLAPS:
            key = tuple(sorted(self.point_key(point) for point in points))
            self.patches.setdefault(key, (points, normal))


def find_contacts(surfaces):
    marks = ContactMarks()
    pairs = []
    for first, second in combinations(surfaces, 2):
        counts = {"SEGMENT": 0, "POINT": 0, "PATCH": 0}
        for i, j in triangle_candidates(first, second, EPSILON):
            result = triangle_intersection(first.triangles[i], second.triangles[j],
                                           first.normals[i], second.normals[j], EPSILON)
            if result is not None:
                kind, points = result
                counts[kind] += 1
                marks.add(kind, points, first.normals[i])
        if any(counts.values()):
            pairs.append((first.name, second.name, counts))
            print(f"Kontakt: {first.name} <-> {second.name} | "
                  f"Dreieckstests mit Treffer: {counts}", flush=True)
    return marks, pairs


# ------------------------------- Darstellung ------------------------------

class PixelOverlay:
    """Projiziert Striche mit fester Pixelbreite auf eine Ebene vor der Kamera."""

    def __init__(self, scene, depsgraph):
        self.scene = scene
        self.depsgraph = depsgraph
        camera = scene.camera
        if camera is None or camera.data.type not in {"PERSP", "ORTHO"}:
            raise RuntimeError('PIXELS benötigt eine aktive Perspektiv- oder Orthokamera. '
                               'Alternativ LINE_WIDTH_MODE = "WORLD" einstellen.')
        self.camera = camera.evaluated_get(depsgraph)
        if self.camera.data.dof.use_dof:
            raise RuntimeError('Für PIXELS die Tiefenschärfe der Kamera ausschalten '
                               'oder LINE_WIDTH_MODE = "WORLD" einstellen.')
        self.matrix = self.camera.matrix_world.normalized()
        self.inverse = self.matrix.inverted()
        self.perspective = self.camera.data.type == "PERSP"
        self.near = float(self.camera.data.clip_start)
        self.far = float(self.camera.data.clip_end)
        self.depth = self.near * 1.001
        scale = scene.render.resolution_percentage / 100.0
        self.width = max(1, int(scene.render.resolution_x * scale))
        self.height = max(1, int(scene.render.resolution_y * scale))
        frame = np.array([tuple(v) for v in self.camera.data.view_frame(scene=scene)])
        if self.perspective:
            frame[:, :2] /= -frame[:, 2, None]
        self.minimum = frame[:, :2].min(axis=0)
        self.extent = frame[:, :2].max(axis=0) - self.minimum
        self.size = np.array((self.width, self.height), dtype=float)
        self.vertices = []
        self.faces = []

    def local_point(self, point):
        return np.array(self.inverse @ Vector(point), dtype=float)

    def project_local(self, point):
        xy = point[:2] / (-point[2]) if self.perspective else point[:2]
        return (xy - self.minimum) / self.extent * self.size

    def world_on_overlay(self, point):
        xy = self.minimum + np.asarray(point) / self.size * self.extent
        if self.perspective:
            xy = xy * self.depth
        return tuple(self.matrix @ Vector((float(xy[0]), float(xy[1]), -self.depth)))

    def polygon(self, points):
        base = len(self.vertices)
        self.vertices.extend(self.world_on_overlay(point) for point in points)
        self.faces.append(tuple(range(base, len(self.vertices))))

    def dot(self, point):
        radius = LINE_WIDTH_PX * 0.5
        self.polygon([point + radius * np.array((math.cos(angle), math.sin(angle)))
                      for angle in np.linspace(0, 2 * math.pi, 24, endpoint=False)])

    def stroke(self, start, end):
        direction = end - start
        length = np.linalg.norm(direction)
        if length > 1e-8:
            side = np.array((-direction[1], direction[0])) / length * LINE_WIDTH_PX * 0.5
            self.polygon([start - side, end - side, end + side, start + side])
        self.dot(start)
        self.dot(end)

    def visible(self, local_point):
        if not RESPECT_OCCLUSION:
            return True
        if self.perspective:
            origin_local = local_point * (self.near / -local_point[2])
        else:
            origin_local = np.array((local_point[0], local_point[1], -self.near))
        origin = self.matrix @ Vector(origin_local)
        target = self.matrix @ Vector(local_point)
        direction = target - origin
        distance = direction.length
        tolerance = max(EPSILON * 8, distance * 1e-6)
        if distance <= tolerance:
            return True
        direction.normalize()
        remaining = distance - tolerance
        for _ in range(64):
            hit, location, _, _, obj, _ = self.scene.ray_cast(
                self.depsgraph, origin, direction, distance=remaining)
            if not hit:
                return True
            skip = (obj.get(OUTPUT_TAG, False) or obj.hide_render
                    or (IGNORE_EDGE_HELPERS and obj.get("_edge_mesh_output", False)))
            if not skip:
                return False
            advance = (location - origin).length + tolerance
            remaining -= advance
            if remaining <= 0:
                return True
            origin = location + tolerance * direction
        return False

    def segment(self, start, end):
        a, b = self.local_point(start), self.local_point(end)
        # Zuerst an den Tiefengrenzen der Kamera abschneiden.
        delta = b - a
        lower, upper = 0.0, 1.0
        da, db = -a[2], -b[2]
        if abs(db - da) < 1e-14:
            if not self.near < da < self.far:
                return
        else:
            bounds = sorted(((self.near * 1.002 - da) / (db - da),
                             (self.far - da) / (db - da)))
            lower, upper = max(lower, bounds[0]), min(upper, bounds[1])
        if lower > upper:
            return
        a, b = a + lower * delta, a + upper * delta
        screen_a, screen_b = self.project_local(a), self.project_local(b)
        screen_delta = screen_b - screen_a
        # Außerhalb des Bildes keine unnötigen Sichtbarkeitstests ausführen.
        lower, upper = 0.0, 1.0
        margin = LINE_WIDTH_PX
        for axis in range(2):
            if abs(screen_delta[axis]) < 1e-12:
                if not -margin <= screen_a[axis] <= self.size[axis] + margin:
                    return
            else:
                bounds = sorted(((-margin - screen_a[axis]) / screen_delta[axis],
                                 (self.size[axis] + margin - screen_a[axis]) / screen_delta[axis]))
                lower, upper = max(lower, bounds[0]), min(upper, bounds[1])
        if lower > upper:
            return
        steps = max(1, int(math.ceil(np.linalg.norm(screen_delta) * (upper - lower))))
        run_start = None
        previous_t = lower
        for t in np.linspace(lower, upper, steps + 1):
            if self.perspective:
                wa, wb = (1 - t) / -a[2], t / -b[2]
                point = (wa * a + wb * b) / (wa + wb)
            else:
                point = (1 - t) * a + t * b
            if self.visible(point):
                if run_start is None:
                    run_start = t
            elif run_start is not None:
                self.stroke(screen_a + run_start * screen_delta,
                            screen_a + previous_t * screen_delta)
                run_start = None
            previous_t = t
        if run_start is not None:
            self.stroke(screen_a + run_start * screen_delta, screen_a + upper * screen_delta)

    def point(self, point):
        local = self.local_point(point)
        if self.near < -local[2] < self.far and self.visible(local):
            screen = self.project_local(local)
            if np.all(screen >= -LINE_WIDTH_PX) and np.all(screen <= self.size + LINE_WIDTH_PX):
                self.dot(screen)


def make_black_material():
    material = next((m for m in bpy.data.materials if m.get(OUTPUT_TAG, False)), None)
    if material is None:
        material = bpy.data.materials.new(MATERIAL_NAME)
    material[OUTPUT_TAG] = True
    material.diffuse_color = (0.0, 0.0, 0.0, 1.0)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    emission.inputs["Strength"].default_value = 1.0
    material.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def add_sphere(vertices, faces, center, radius, sides=16, rings=8):
    north = len(vertices)
    vertices.append(tuple(center + np.array((0, 0, radius))))
    first_ring = len(vertices)
    for ring in range(1, rings):
        latitude = math.pi * ring / rings
        for side in range(sides):
            angle = 2.0 * math.pi * side / sides
            vertices.append(tuple(center + radius * np.array((
                math.sin(latitude) * math.cos(angle),
                math.sin(latitude) * math.sin(angle), math.cos(latitude)))))
    south = len(vertices)
    vertices.append(tuple(center - np.array((0, 0, radius))))
    last_ring = first_ring + (rings - 2) * sides
    for i in range(sides):
        j = (i + 1) % sides
        faces.extend(((north, first_ring + i, first_ring + j),
                      (last_ring + i, south, last_ring + j)))
    for ring in range(rings - 2):
        upper = first_ring + ring * sides
        lower = upper + sides
        for i in range(sides):
            j = (i + 1) % sides
            faces.append((upper + i, lower + i, lower + j, upper + j))


def remove_output(obj):
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data.users == 0:
        if isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
        elif isinstance(data, bpy.types.Curve):
            bpy.data.curves.remove(data)


def build_highlights(marks, pair_count):
    line_radius = LINE_DIAMETER * 0.5
    overlay = None
    if LINE_WIDTH_MODE == "PIXELS":
        overlay = PixelOverlay(bpy.context.scene, bpy.context.evaluated_depsgraph_get())
        for start, end in marks.segments.values():
            overlay.segment(start, end)
        for point in marks.points.values():
            overlay.point(point)
    old_outputs = [obj for obj in bpy.context.scene.objects if obj.get(OUTPUT_TAG, False)]
    collection = bpy.data.collections.get(OUTPUT_COLLECTION_NAME)
    if collection is None:
        collection = bpy.data.collections.new(OUTPUT_COLLECTION_NAME)
    if collection not in tuple(bpy.context.scene.collection.children_recursive):
        bpy.context.scene.collection.children.link(collection)
    collection.hide_render = False
    material = make_black_material()
    created = []

    def link_output(name, data):
        obj = bpy.data.objects.new(name, data)
        obj[OUTPUT_TAG] = True
        obj["contact_object_pairs"] = pair_count
        obj["source_frame"] = bpy.context.scene.frame_current
        created.append(obj)
        collection.objects.link(obj)
        obj.data.materials.append(material)
        if hasattr(obj, "visible_shadow"):
            obj.visible_shadow = False
        return obj

    try:
        if overlay is not None and overlay.faces:
            mesh = bpy.data.meshes.new("CollisionLines_Pixels_Data")
            obj = link_output("CollisionLines_Pixels", mesh)
            obj["line_width_pixels"] = LINE_WIDTH_PX
            obj["render_width"] = overlay.width
            obj["render_height"] = overlay.height
            mesh.from_pydata(overlay.vertices, [], overlay.faces)
            mesh.update()
            for visibility in ("visible_shadow", "visible_diffuse", "visible_glossy",
                               "visible_transmission", "visible_volume_scatter"):
                if hasattr(obj, visibility):
                    setattr(obj, visibility, False)
        if overlay is None and marks.segments:
            curve = bpy.data.curves.new("CollisionLines_Data", "CURVE")
            link_output("CollisionLines", curve)
            curve.dimensions = "3D"
            curve.resolution_u = 1
            curve.bevel_depth = line_radius
            curve.bevel_resolution = CURVE_BEVEL_RESOLUTION
            curve.fill_mode = "FULL"
            curve.use_fill_caps = True
            for start, end in marks.segments.values():
                spline = curve.splines.new("POLY")
                spline.points.add(1)
                spline.points[0].co = (*start, 1.0)
                spline.points[1].co = (*end, 1.0)
                spline.points[0].radius = 1.0
                spline.points[1].radius = 1.0

        vertices, faces = [], []
        offset = max(EPSILON * 4.0, line_radius * 0.02)
        for polygon, normal in marks.patches.values():
            for sign in (-1.0, 1.0):
                base = len(vertices)
                vertices.extend(tuple(point + sign * offset * normal) for point in polygon)
                indices = list(range(base, len(vertices)))
                faces.append(tuple(indices if sign > 0 else reversed(indices)))
        if faces:
            mesh = bpy.data.meshes.new("CollisionAreas_Data")
            link_output("CollisionAreas", mesh)
            mesh.from_pydata(vertices, [], faces)
            mesh.update()

        # Kugeln schließen Linienenden rund und markieren einzelne Kontakte.
        joints = {}
        for start, end in (marks.segments.values() if overlay is None else []):
            for point in (start, end):
                joints.setdefault(marks.point_key(point), (point, line_radius))
        for key, point in (marks.points.items() if overlay is None else []):
            # Dreiecksteilungen können zusätzliche Punkte auf einer Linie liefern.
            on_segment = False
            for start, end in marks.segments.values():
                direction = end - start
                t = np.clip(np.dot(point - start, direction) / np.dot(direction, direction), 0, 1)
                if np.linalg.norm(point - start - t * direction) <= EPSILON:
                    on_segment = True
                    break
            if not on_segment:
                joints[key] = (point, line_radius)
        vertices, faces = [], []
        for point, radius in joints.values():
            add_sphere(vertices, faces, point, radius)
        if faces:
            mesh = bpy.data.meshes.new("CollisionPoints_Data")
            link_output("CollisionPoints", mesh)
            mesh.from_pydata(vertices, [], faces)
            for polygon in mesh.polygons:
                polygon.use_smooth = True
            mesh.update()
    except Exception:
        for obj in created:
            remove_output(obj)
        raise

    # Erst nach erfolgreichem Aufbau die eigene vorige Ausgabe entfernen.
    for obj in old_outputs:
        remove_output(obj)
    bpy.context.view_layer.update()
    return created


def main():
    if SOURCE_MODE not in {"ALL_MESH_OBJECTS", "SELECTED"}:
        raise ValueError('SOURCE_MODE muss "ALL_MESH_OBJECTS" oder "SELECTED" sein.')
    if LINE_WIDTH_MODE not in {"PIXELS", "WORLD"}:
        raise ValueError('LINE_WIDTH_MODE muss "PIXELS" oder "WORLD" sein.')
    for name, value in (("EPSILON", EPSILON), ("LINE_WIDTH_PX", LINE_WIDTH_PX), ("LINE_DIAMETER", LINE_DIAMETER)):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} muss positiv und endlich sein.")
    if bpy.context.mode != "OBJECT":
        raise RuntimeError("Bitte vor dem Ausführen in den Object Mode wechseln.")
    sources = get_source_objects()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    surfaces = []
    for obj in sources:
        surface = read_surface(obj, depsgraph)
        if surface is not None:
            surfaces.append(surface)
        else:
            print(f"Übersprungen (keine auswertbaren Flächen): {obj.name}")
    if len(surfaces) < 2:
        raise RuntimeError("Weniger als zwei Mesh-Objekte mit Flächen gefunden. "
                           "Lose Kanten und Punkte reichen für diesen Test nicht aus.")
    print(f"Prüfe {len(surfaces)} Meshes mit "
          f"{sum(len(s.triangles) for s in surfaces)} Dreiecken ...", flush=True)
    marks, pairs = find_contacts(surfaces)
    created = build_highlights(marks, len(pairs))
    print(f"Fertig: {len(pairs)} Objektpaare mit Oberflächenkontakt; "
          f"{len(marks.segments)} Liniensegmente, {len(marks.patches)} Flächenstücke. "
          f"Markierungen: {OUTPUT_COLLECTION_NAME}. "
          "Nach Änderungen an Modell, Kamera oder Auflösung erneut ausführen.", flush=True)
    return marks, pairs, created


if __name__ == "__main__":
    main()
