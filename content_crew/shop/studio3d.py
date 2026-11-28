"""Fotostudio in Blender: fotorealistische Produktbilder für den Shop.

Jedes Produkt ist ein 3D-Modell in echten Maßen (Meter), ausgeleuchtet wie im Fotostudio und mit Cycles gerendert.
Das Skript läuft innerhalb von Blender (nicht im normalen Python):

    blender -b --factory-startup -P content_crew/shop/studio3d.py -- --out data/shop/studio --only massageball

Optionen: --only (Komma-Liste von Bild-Schlüsseln), --size (Kantenlänge in Pixel), --samples, --art (Ordner mit den
Poster- und Wallpaper-Motiven). Ohne --only entstehen alle Bilder.
"""

from __future__ import annotations

import argparse
import functools
import math
import random
import sys
from itertools import pairwise
from pathlib import Path

# isort: off
import bpy  # zuerst laden: erst danach gibt es bmesh und mathutils
import bmesh
from mathutils import Euler, Vector
from mathutils.bvhtree import BVHTree
# isort: on

# ----------------------------------------------------------------------------- Grundlagen


def clear() -> None:
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
                 bpy.data.curves, bpy.data.metaballs, bpy.data.images, bpy.data.textures):
        for item in list(coll):
            coll.remove(item)


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def setup_render(size: int, samples: int, exposure: float = 0.0, view: str = "neutral") -> None:
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    try:  # Rauschfilter (in der offiziellen Blender-Version enthalten, in manchen Linux-Paketen nicht)
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
        sc.cycles.use_denoising = True
    except TypeError:
        sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 10
    sc.cycles.diffuse_bounces = 4
    sc.cycles.glossy_bounces = 4
    sc.cycles.transmission_bounces = 10
    sc.cycles.transparent_max_bounces = 10
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.blur_glossy = 0.6
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 92
    # Produktfotos: „Khronos PBR Neutral“ zeigt Materialfarben unverfälscht (ab Blender 4.2), sonst AgX
    views = [v.identifier for v in sc.view_settings.bl_rna.properties["view_transform"].enum_items]
    if view == "neutral" and "Khronos PBR Neutral" in views:
        sc.view_settings.view_transform = "Khronos PBR Neutral"
    else:
        sc.view_settings.view_transform = "AgX"
        for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
            try:
                sc.view_settings.look = look
                break
            except TypeError:
                continue
    sc.view_settings.exposure = exposure


def world(color=(0.93, 0.93, 0.95), strength: float = 0.35) -> None:
    w = bpy.data.worlds[0] if bpy.data.worlds else bpy.data.worlds.new("Welt")
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (*color, 1)
    bg.inputs[1].default_value = strength


def world_gradient(horizon, zenith, strength: float = 1.0) -> None:
    """Himmel mit hellem Horizont und blauem Zenit – gibt Lack und Glas glaubhafte Spiegelungen."""
    w = bpy.data.worlds[0] if bpy.data.worlds else bpy.data.worlds.new("Welt")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (*horizon, 1)
    ramp.color_ramp.elements[1].position = 0.6
    ramp.color_ramp.elements[1].color = (*zenith, 1)
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs[0])
    bg.inputs[1].default_value = strength


def look_at(ob, target) -> None:
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def camera(loc, target, lens: float = 70, fstop: float | None = None, shift=(0.0, 0.0)):
    cd = bpy.data.cameras.new("Kamera")
    cd.lens = lens
    cd.sensor_width = 36
    cd.shift_x, cd.shift_y = shift
    ob = link(bpy.data.objects.new("Kamera", cd))
    ob.location = Vector(loc)
    look_at(ob, target)
    if fstop:
        cd.dof.use_dof = True
        cd.dof.focus_distance = (Vector(target) - Vector(loc)).length
        cd.dof.aperture_fstop = fstop
    bpy.context.scene.camera = ob
    return ob


def area(loc, target, size: float, power: float, color=(1, 1, 1), size_y: float | None = None, visible=False):
    ld = bpy.data.lights.new("Licht", "AREA")
    ld.energy = power
    ld.color = color
    ld.size = size
    if size_y:
        ld.shape = "RECTANGLE"
        ld.size_y = size_y
    else:
        ld.shape = "DISK"
    ob = link(bpy.data.objects.new("Licht", ld))
    ob.location = Vector(loc)
    look_at(ob, target)
    ob.visible_camera = visible
    return ob


def sun(direction, strength: float = 3.0, angle: float = 2.0, color=(1, 0.96, 0.9)):
    ld = bpy.data.lights.new("Sonne", "SUN")
    ld.energy = strength
    ld.angle = math.radians(angle)
    ld.color = color
    ob = link(bpy.data.objects.new("Sonne", ld))
    ob.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()
    return ob


def studio_lights(target, S: float, key: float = 1.0, warm: bool = False) -> None:
    """Softbox links vorne, Aufheller rechts, Kante von hinten, weiche Decke."""
    t = Vector(target)
    kc = (1.0, 0.95, 0.88) if warm else (1.0, 0.98, 0.95)
    area(t + Vector((-1.5, -1.6, 1.9)) * S, t, 1.5 * S, 95 * S * S * key, kc)
    area(t + Vector((2.0, -0.9, 0.8)) * S, t, 2.2 * S, 24 * S * S * key, (0.95, 0.97, 1.0))
    area(t + Vector((0.5, 2.3, 2.0)) * S, t, 1.3 * S, 80 * S * S * key)
    area(t + Vector((0.0, -0.3, 3.2)) * S, t, 3.0 * S, 30 * S * S * key)


# ----------------------------------------------------------------------------- Materialien

_KEYS = {"sheen": "Sheen Weight", "sheen_rough": "Sheen Roughness", "sheen_tint": "Sheen Tint", "coat": "Coat Weight",
         "coat_rough": "Coat Roughness", "sss": "Subsurface Weight", "sss_radius": "Subsurface Radius",
         "sss_scale": "Subsurface Scale", "trans": "Transmission Weight", "ior": "IOR", "aniso": "Anisotropic",
         "aniso_rot": "Anisotropic Rotation", "spec": "Specular IOR Level", "alpha": "Alpha",
         "emit": "Emission Color", "emit_strength": "Emission Strength"}


def mat(name: str, color, rough: float = 0.5, metal: float = 0.0, **kw):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    for k, v in kw.items():
        inp = b.inputs[_KEYS[k]]
        if isinstance(v, (tuple, list)) and len(v) == 3 and inp.type == "RGBA":
            v = (*v, 1)
        inp.default_value = v
    return m


def _nodes(m):
    nt = m.node_tree
    return nt, nt.nodes["Principled BSDF"]


def _coords(nt, coords: str = "Object", scale=(1, 1, 1), rotation=(0, 0, 0)):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = scale
    mp.inputs["Rotation"].default_value = rotation
    nt.links.new(tc.outputs[coords], mp.inputs["Vector"])
    return mp.outputs["Vector"]


def bump(m, height_socket, strength: float = 0.3, distance: float = 0.0005):
    nt, b = _nodes(m)
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = strength
    bp.inputs["Distance"].default_value = distance
    nt.links.new(height_socket, bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return bp


def noise(nt, vec, scale: float, detail: float = 6, rough: float = 0.6):
    tx = nt.nodes.new("ShaderNodeTexNoise")
    tx.inputs["Scale"].default_value = scale
    tx.inputs["Detail"].default_value = detail
    tx.inputs["Roughness"].default_value = rough
    nt.links.new(vec, tx.inputs["Vector"])
    return tx


def wave(nt, vec, scale: float, direction: str = "X", distortion: float = 0.0, profile: str = "SIN"):
    tx = nt.nodes.new("ShaderNodeTexWave")
    tx.wave_type = "BANDS"
    tx.bands_direction = direction
    tx.wave_profile = profile
    tx.inputs["Scale"].default_value = scale
    tx.inputs["Distortion"].default_value = distortion
    nt.links.new(vec, tx.inputs["Vector"])
    return tx


def math_node(nt, op: str, a, b=None, value: float | None = None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    nt.links.new(a, n.inputs[0])
    if b is not None:
        nt.links.new(b, n.inputs[1])
    elif value is not None:
        n.inputs[1].default_value = value
    return n.outputs[0]


def fabric(name: str, color, weave: float = 900, strength: float = 0.35, sheen: float = 0.6, rough: float = 0.9,
           fuzz: float = 0.0, coords: str = "Object"):
    """Gewebe: zwei gekreuzte Wellen als Fadenstruktur, dazu feines Rauschen."""
    m = mat(name, color, rough, sheen=sheen, sheen_rough=0.45)
    nt, b = _nodes(m)
    v = _coords(nt, coords)
    a = wave(nt, v, weave, "X").outputs["Fac"]
    c = wave(nt, v, weave, "Y").outputs["Fac"]
    h = math_node(nt, "MULTIPLY", a, c)
    n = noise(nt, v, weave * 0.6, 4).outputs["Fac"]
    h = math_node(nt, "ADD", h, math_node(nt, "MULTIPLY", n, value=0.6 + fuzz))
    bump(m, h, strength, 0.0004)
    if fuzz:  # leichte Farbschwankung wie bei Fleece
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.inputs["A"].default_value = (*[x * 0.82 for x in color], 1)
        mix.inputs["B"].default_value = (*color, 1)
        nt.links.new(noise(nt, v, 200, 3).outputs["Fac"], mix.inputs["Factor"])
        nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    return m


def knit(name: str, color, rib: float = 260, strength: float = 0.5, direction: str = "Z"):
    """Strick/Rippen: kräftige Wellen in einer Richtung plus Gewebe."""
    m = mat(name, color, 0.92, sheen=0.7, sheen_rough=0.5)
    nt, _ = _nodes(m)
    v = _coords(nt)
    r = wave(nt, v, rib, direction).outputs["Fac"]
    n = noise(nt, v, 1400, 3).outputs["Fac"]
    bump(m, math_node(nt, "ADD", r, math_node(nt, "MULTIPLY", n, value=0.35)), strength, 0.0006)
    return m


def brushed(name: str, color=(0.80, 0.81, 0.83), rough: float = 0.3, axis: str = "X"):
    """Gebürstetes, eloxiertes Aluminium."""
    m = mat(name, color, rough, 1.0, aniso=0.6)
    nt, _ = _nodes(m)
    sc = {"X": (2, 900, 900), "Y": (900, 2, 900), "Z": (900, 900, 2)}[axis]
    v = _coords(nt, "Object", sc)
    bump(m, noise(nt, v, 1.0, 2).outputs["Fac"], 0.04, 0.0002)
    return m


def plastic(name: str, color, rough: float = 0.35, coat: float = 0.0):
    m = mat(name, color, rough, coat=coat, coat_rough=0.08)
    nt, _ = _nodes(m)
    bump(m, noise(nt, _coords(nt), 3000, 2).outputs["Fac"], 0.03, 0.0002)
    return m


def rubber(name: str, color, rough: float = 0.55):
    m = mat(name, color, rough, sss=0.15, sss_radius=(0.004, 0.003, 0.002), sss_scale=0.01, spec=0.4)
    nt, _ = _nodes(m)
    bump(m, noise(nt, _coords(nt), 2500, 3).outputs["Fac"], 0.08, 0.0002)
    return m


def clear_plastic(name: str, tint=(0.96, 0.98, 1.0), rough: float = 0.04):
    return mat(name, tint, rough, trans=1.0, ior=1.49, spec=0.5)


def see_through(*objects) -> None:
    """Durchsichtige Teile werfen keinen harten Schatten – so bleibt Licht hinter Folie und Acryl."""
    for ob in objects:
        ob.visible_shadow = False


def image_mat(name: str, path: str, rough: float = 0.5, emission: float = 0.0, base_dark: bool = False):
    m = mat(name, (1, 1, 1), rough)
    nt, b = _nodes(m)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(path))
    tex.interpolation = "Cubic"
    tex.extension = "EXTEND"
    if emission:
        nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emission
        b.inputs["Base Color"].default_value = (0.01, 0.01, 0.01, 1) if base_dark else (1, 1, 1, 1)
        b.inputs["Roughness"].default_value = 0.06
    else:
        nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    return m


def wood(name: str, light=(0.62, 0.45, 0.29), dark=(0.42, 0.28, 0.16), scale: float = 1.0, planks: bool = False,
         rough: float = 0.45, along: str = "X"):
    """Eichenholz: Maserung aus verzerrten Wellen, wahlweise als Dielenboden."""
    m = mat(name, light, rough, coat=0.25 if not planks else 0.15, coat_rough=0.25)
    nt, b = _nodes(m)
    stretch = {"X": (0.35, 6.0, 6.0), "Y": (6.0, 0.35, 6.0)}[along]
    v = _coords(nt, "Object", tuple(s / scale for s in stretch))
    grain = wave(nt, v, 3.0, "Y" if along == "X" else "X", distortion=6.0)
    grain.inputs["Detail"].default_value = 4
    grain.inputs["Detail Scale"].default_value = 1.5
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*dark, 1)
    ramp.color_ramp.elements[1].color = (*light, 1)
    nt.links.new(grain.outputs["Fac"], ramp.inputs["Fac"])
    color = ramp.outputs["Color"]
    if planks:
        br = nt.nodes.new("ShaderNodeTexBrick")
        br.offset = 0.5
        br.offset_frequency = 1
        br.inputs["Scale"].default_value = 1.0
        br.inputs["Mortar Size"].default_value = 0.002
        br.inputs["Brick Width"].default_value = 1.4 if along == "X" else 0.18
        br.inputs["Row Height"].default_value = 0.18 if along == "X" else 1.4
        br.inputs["Color1"].default_value = (1.0, 1.0, 1.0, 1)
        br.inputs["Color2"].default_value = (0.78, 0.74, 0.70, 1)
        br.inputs["Mortar"].default_value = (0.18, 0.12, 0.08, 1)
        nt.links.new(_coords(nt, "Object"), br.inputs["Vector"])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        nt.links.new(color, mix.inputs["A"])
        nt.links.new(br.outputs["Color"], mix.inputs["B"])
        color = mix.outputs["Result"]
        bump(m, br.outputs["Fac"], 0.25, 0.001)
    nt.links.new(color, b.inputs["Base Color"])
    return m


def plaster(name: str, color=(0.86, 0.84, 0.80)):
    m = mat(name, color, 0.85)
    nt, _ = _nodes(m)
    bump(m, noise(nt, _coords(nt), 60, 8, 0.65).outputs["Fac"], 0.12, 0.002)
    return m


# ----------------------------------------------------------------------------- Formen


def _finish(ob, smooth: bool = True, angle: float = 40.0):
    me = ob.data
    if smooth and hasattr(me, "polygons"):
        for p in me.polygons:
            p.use_smooth = True
        if hasattr(me, "use_auto_smooth"):
            me.use_auto_smooth = True
            me.auto_smooth_angle = math.radians(angle)
    return ob


def mesh_object(name: str, bm, material=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new(name, me))
    ob.location = Vector(loc)
    ob.rotation_euler = Euler(rot)
    if material:
        me.materials.append(material)
    return ob


def bevel_mod(ob, width: float, segments: int = 5, harden: bool = True, angle: float | None = None):
    md = ob.modifiers.new("Kante", "BEVEL")
    md.width = width
    md.segments = segments
    md.limit_method = "ANGLE" if angle else "NONE"
    if angle:
        md.angle_limit = math.radians(angle)
    md.harden_normals = harden
    _finish(ob)
    return md


def box(name: str, size, material=None, loc=(0, 0, 0), rot=(0, 0, 0), bevel: float = 0.0, segments: int = 5):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    ob = mesh_object(name, bm, material, loc, rot)
    if bevel:
        bevel_mod(ob, bevel, segments)
    return ob


def cylinder(name: str, radius: float, depth: float, material=None, loc=(0, 0, 0), rot=(0, 0, 0),
             bevel: float = 0.0, verts: int = 64, radius2: float | None = None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=verts, radius1=radius,
                          radius2=radius if radius2 is None else radius2, depth=depth)
    ob = mesh_object(name, bm, material, loc, rot)
    if bevel:
        bevel_mod(ob, bevel, 4, angle=30)
    else:
        _finish(ob)
    return ob


def sphere(name: str, radius: float, material=None, loc=(0, 0, 0), subdiv: int = 5, scale=(1, 1, 1)):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    ob = mesh_object(name, bm, material, loc)
    ob.scale = scale
    return _finish(ob)


def torus(name: str, R: float, r: float, material=None, loc=(0, 0, 0), rot=(0, 0, 0), seg=(96, 24)):
    bm = bmesh.new()
    verts = []
    for i in range(seg[0]):
        a = 2 * math.pi * i / seg[0]
        ring = []
        for j in range(seg[1]):
            b = 2 * math.pi * j / seg[1]
            ring.append(bm.verts.new(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a),
                                      r * math.sin(b))))
        verts.append(ring)
    for i in range(seg[0]):
        for j in range(seg[1]):
            bm.faces.new((verts[i][j], verts[(i + 1) % seg[0]][j], verts[(i + 1) % seg[0]][(j + 1) % seg[1]],
                          verts[i][(j + 1) % seg[1]]))
    return _finish(mesh_object(name, bm, material, loc, rot))


def rounded_rect(name: str, w: float, h: float, r: float, material=None, loc=(0, 0, 0), rot=(0, 0, 0),
                 thickness: float = 0.0, segs: int = 10, uv: bool = True):
    """Flache Platte mit runden Ecken (UV 0..1 über die ganze Fläche, z. B. für Bildschirme und Poster)."""
    bm = bmesh.new()
    pts = []
    r = min(r, w / 2 - 1e-5, h / 2 - 1e-5)
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180),
                       (w / 2 - r, -h / 2 + r, 270)):
        for i in range(segs + 1):
            a = math.radians(a0 + 90 * i / segs)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    face = bm.faces.new([bm.verts.new((x, y, 0)) for x, y in pts])
    if uv:
        layer = bm.loops.layers.uv.new()
        for loop in face.loops:
            loop[layer].uv = (loop.vert.co.x / w + 0.5, loop.vert.co.y / h + 0.5)
    if thickness:
        ext = bmesh.ops.extrude_face_region(bm, geom=[face])
        moved = [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, vec=(0, 0, -thickness), verts=moved)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_object(name, bm, material, loc, rot)
    return ob


def tube_curve(name: str, points, radius: float, material=None, caps: bool = True, resolution: int = 24,
               bevel_res: int = 8):
    cd = bpy.data.curves.new(name, "CURVE")
    cd.dimensions = "3D"
    cd.resolution_u = resolution
    cd.bevel_depth = radius
    cd.bevel_resolution = bevel_res
    cd.use_fill_caps = caps
    sp = cd.splines.new("BEZIER")
    sp.bezier_points.add(len(points) - 1)
    for bp, p in zip(sp.bezier_points, points):
        bp.co = Vector(p)
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    ob = link(bpy.data.objects.new(name, cd))
    if material:
        cd.materials.append(material)
    return ob


def metaball(name: str, elements: list[dict], material=None, resolution: float = 0.004, threshold: float = 0.6,
             loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    mb = bpy.data.metaballs.new(name)
    mb.resolution = resolution
    mb.render_resolution = resolution * 0.5
    mb.threshold = threshold
    ob = link(bpy.data.objects.new(name, mb))
    for e in elements:
        el = mb.elements.new(type=e.get("type", "BALL"))
        el.co = Vector(e["co"])
        el.radius = e["r"]
        el.stiffness = e.get("stiff", 2.0)
        if "size" in e:
            el.size_x, el.size_y, el.size_z = e["size"]
        if "rot" in e:
            el.rotation = Euler(e["rot"]).to_quaternion()
    if material:
        mb.materials.append(material)
    ob.location = Vector(loc)
    ob.rotation_euler = Euler(rot)
    ob.scale = scale
    return ob


def to_mesh(ob, name: str | None = None):
    """Metaball/Kurve in ein echtes Netz umwandeln (für Strahltests und Modifikatoren)."""
    deps = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(deps))
    new = link(bpy.data.objects.new(name or ob.name + "_netz", me))
    new.matrix_world = ob.matrix_world.copy()
    bpy.data.objects.remove(ob)
    return _finish(new)


def subdivide(ob, levels: int = 2):
    md = ob.modifiers.new("Glatt", "SUBSURF")
    md.levels = md.render_levels = levels
    return md


def displace(ob, strength: float, size: float, depth: int = 2, kind: str = "CLOUDS", midlevel: float = 0.5):
    tex = bpy.data.textures.new(ob.name + "_tex", kind)
    if kind == "CLOUDS":
        tex.noise_scale = size
        tex.noise_depth = depth
    md = ob.modifiers.new("Falten", "DISPLACE")
    md.texture = tex
    md.strength = strength
    md.mid_level = midlevel
    md.texture_coords = "GLOBAL"
    return md


def cyclorama(S: float, color=(0.93, 0.92, 0.90), back: float = 1.0, height: float = 3.0, radius: float = 0.8,
              material=None):
    """Hohlkehle wie im Fotostudio: Boden geht nahtlos in die Rückwand über."""
    prof = [(-4.0, 0.0), (back - radius, 0.0)]
    for i in range(1, 25):
        t = (math.pi / 2) * i / 24
        prof.append((back - radius + radius * math.sin(t), radius - radius * math.cos(t)))
    prof.append((back, height))
    bm = bmesh.new()
    rows = []
    for x in (-5.0, 5.0):
        rows.append([bm.verts.new((x * S, y * S, z * S)) for y, z in prof])
    for i in range(len(prof) - 1):
        bm.faces.new((rows[0][i], rows[1][i], rows[1][i + 1], rows[0][i + 1]))
    m = material or mat("Studio", color, 0.75)
    return _finish(mesh_object("Hohlkehle", bm, m), angle=80)


def contact_floor(S: float, material):
    return box("Boden", (12 * S, 12 * S, 0.01), material, (0, 0, -0.005))


# ----------------------------------------------------------------------------- Produkte
# Jede Funktion baut das Produkt und gibt die Kamera vor: dict(target, S, cam, lens, fstop, exposure, backdrop).


def mbr(surface: float, stiff: float = 2.0, thr: float = 0.6) -> float:
    """Metaball-Radius für eine gewünschte sichtbare Rundung (Feld (1-d²/r²)³ · Steifigkeit = Schwelle)."""
    return surface / math.sqrt(1 - (thr / stiff) ** (1 / 3))


def group(name: str, objects, loc=(0, 0, 0), rot=(0, 0, 0)):
    e = link(bpy.data.objects.new(name, None))
    for o in objects:
        o.parent = e
    e.location = Vector(loc)
    e.rotation_euler = Euler(rot)
    return e


def lowest_z(objects) -> float:
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    zs = []
    for ob in objects:
        ev = ob.evaluated_get(deps)
        zs += [(ob.matrix_world @ Vector(c)).z for c in ev.bound_box]
    return min(zs)


def bar(name: str, p0, p1, material, w: float, t: float, bevel: float = 0.002):
    """Flache Leiste zwischen zwei Punkten in der YZ-Ebene."""
    v = Vector(p1) - Vector(p0)
    ob = box(name, (w, v.length, t), material, (Vector(p0) + Vector(p1)) / 2, bevel=bevel, segments=3)
    ob.rotation_euler = (math.atan2(v.z, v.y), 0, 0)
    return ob


def lathe(name: str, profile, material, segs: int = 72, loc=(0, 0, 0)):
    """Drehkörper aus einem Profil [(Radius, Höhe), …] – Reihenfolge außen hoch, innen runter."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        if r < 1e-6:
            pole = bm.verts.new((0, 0, z))
            rings.append([pole] * segs)
        else:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / segs), r * math.sin(2 * math.pi * i / segs), z))
                          for i in range(segs)])
    for a, b in pairwise(rings):
        for i in range(segs):
            j = (i + 1) % segs
            vs = []
            for v in (a[i], a[j], b[j], b[i]):
                if v not in vs:
                    vs.append(v)
            if len(vs) >= 3:
                bm.faces.new(vs)
    return _finish(mesh_object(name, bm, material, loc), angle=60)


def outline(name: str, pts, thickness: float, material, loc=(0, 0, 0), rot=(0, 0, 0), bevel: float = 0.0):
    """2D-Umriss (x, y) als flaches Teil mit Dicke."""
    bm = bmesh.new()
    face = bm.faces.new([bm.verts.new((x, y, 0)) for x, y in pts])
    ext = bmesh.ops.extrude_face_region(bm, geom=[face])
    bmesh.ops.translate(bm, vec=(0, 0, thickness),
                        verts=[e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_object(name, bm, material, loc, rot)
    if bevel:
        bevel_mod(ob, bevel, 3, angle=30)
    return ob


def band_ring(name: str, R: float, W: float, t: float, material, segs: int = 160):
    """Breites Ringband (Querschnitt: Stadion aus Breite W und Dicke t)."""
    bm = bmesh.new()
    rr = t / 2
    prof = []
    for cx, cz, a0 in ((0.0, W / 2 - rr, 0), (0.0, W / 2 - rr, 90), (0.0, -W / 2 + rr, 180), (0.0, -W / 2 + rr, 270)):
        for i in range(7):
            a = math.radians(a0 + 90 * i / 6)
            prof.append((cx + rr * math.cos(a), cz + rr * math.sin(a)))
    rings = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        rings.append([bm.verts.new(((R + dr) * math.cos(a), (R + dr) * math.sin(a), dz)) for dr, dz in prof])
    n = len(prof)
    for i in range(segs):
        for j in range(n):
            bm.faces.new((rings[i][j], rings[(i + 1) % segs][j], rings[(i + 1) % segs][(j + 1) % n],
                          rings[i][(j + 1) % n]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _finish(mesh_object(name, bm, material), angle=50)


def hair(name: str, center, n: int, length: float, color, spread: float = 0.03, seed: int = 1):
    """Lose Tierhaare auf dem Boden."""
    rnd = random.Random(seed)
    cd = bpy.data.curves.new(name, "CURVE")
    cd.dimensions = "3D"
    cd.bevel_depth = 0.00016
    cd.bevel_resolution = 1
    for _ in range(n):
        sp = cd.splines.new("POLY")
        sp.points.add(3)
        x0 = center[0] + rnd.gauss(0, spread)
        y0 = center[1] + rnd.gauss(0, spread * 0.5)
        ang = rnd.uniform(0, 2 * math.pi)
        L = length * rnd.uniform(0.5, 1.2)
        for k in range(4):
            t = k / 3
            sp.points[k].co = (x0 + math.cos(ang) * L * t + rnd.uniform(-0.002, 0.002),
                               y0 + math.sin(ang) * L * t + rnd.uniform(-0.002, 0.002),
                               0.0003 + 0.0015 * math.sin(math.pi * t), 1)
    cd.materials.append(mat(name, color, 0.45, sheen=0.6))
    return link(bpy.data.objects.new(name, cd))


def phone(tag: str, screen_img: Path | None, body_color=(0.06, 0.065, 0.075), emission: float = 1.6):
    """Smartphone (19,5:9) mit Bild auf dem Display; Bildschirm zeigt nach +Z, Mitte im Ursprung."""
    frame = mat(f"Rahmen{tag}", body_color, 0.25, 0.9)
    glass = mat(f"Glas{tag}", (0.004, 0.004, 0.005), 0.04, spec=0.6)
    parts = [rounded_rect(f"Handy{tag}", 0.0715, 0.1475, 0.011, frame, (0, 0, 0), thickness=0.0078, uv=False)]
    bevel_mod(parts[0], 0.0016, 4, angle=40)
    parts.append(rounded_rect(f"Glas{tag}", 0.0705, 0.1465, 0.0105, glass, (0, 0, 0.0002), uv=False))
    if screen_img and Path(screen_img).exists():
        parts.append(rounded_rect(f"Bild{tag}", 0.0672, 0.1432, 0.0095,
                                  image_mat(f"Display{tag}", screen_img, emission=emission, base_dark=True),
                                  (0, 0, 0.00035)))
    return parts


# ----------------------------------------------------------------------------- Produkte
# Jede Funktion baut das Produkt und gibt die Kamera vor: dict(target, S, cam, lens, fstop, exposure, …).


def massageball(art: Path) -> dict:
    teal = rubber("Teal", (0.03, 0.36, 0.40), 0.5)
    coral = rubber("Koralle", (0.85, 0.27, 0.18), 0.45)
    r = 0.036
    core = sphere("Igelball", r, teal, (0.05, 0.035, r + 0.0118))
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    dirs = [v.co.normalized() for v in bm.verts]
    bm.free()
    spike = bmesh.new()
    bmesh.ops.create_cone(spike, cap_ends=True, segments=16, radius1=0.0055, radius2=0.0018, depth=0.012)
    bmesh.ops.translate(spike, vec=(0, 0, 0.006), verts=spike.verts)
    sm = bpy.data.meshes.new("Noppe")
    spike.to_mesh(sm)
    spike.free()
    for poly in sm.polygons:
        poly.use_smooth = True
    sm.materials.append(teal)
    for i, d in enumerate(dirs):
        ob = link(bpy.data.objects.new(f"Noppe{i}", sm))
        ob.location = core.location + d * (r - 0.001)
        ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    duo = metaball("Duoball", [{"co": (-0.032, 0, 0), "r": 0.06}, {"co": (0.032, 0, 0), "r": 0.06}], coral,
                   resolution=0.003, loc=(-0.055, -0.04, 0.0), rot=(0, 0, math.radians(-28)))
    duo.location.z -= lowest_z([duo]) - 0.005
    matte = rubber("Yogamatte", (0.30, 0.36, 0.32), 0.8)
    box("Yogamatte", (0.7, 0.45, 0.005), matte, (0.03, 0.06, 0.0025), (0, 0, math.radians(8)), bevel=0.0022)
    return {"target": (0.0, 0.0, 0.04), "S": 0.3, "cam": (-0.16, -0.62, 0.3), "lens": 85, "fstop": 8}


def eiskratzer(art: Path) -> dict:
    blue = mat("Kratzer", (0.02, 0.2, 0.62), 0.12, trans=0.55, ior=1.5, coat=0.4, coat_rough=0.05)
    shell = mat("Handschuh", (0.012, 0.013, 0.016), 0.42, coat=0.2, coat_rough=0.3)
    nt, _ = _nodes(shell)
    qv = _coords(nt)
    bump(shell, math_node(nt, "ADD", wave(nt, qv, 38, "X", profile="SIN").outputs["Fac"],
                          math_node(nt, "MULTIPLY", noise(nt, qv, 900, 3).outputs["Fac"], value=0.15)), 0.55, 0.003)
    fleece = fabric("Fleece", (0.86, 0.82, 0.74), weave=600, strength=0.7, sheen=1.0, rough=1.0, fuzz=0.8)

    def unit(tag: str):
        L, wf, wb, tb, tf = 0.10, 0.118, 0.07, 0.0075, 0.0025
        bm = bmesh.new()
        pts = [(-wb / 2, 0.0), (wb / 2, 0.0), (wf / 2, L), (-wf / 2, L)]
        bot = [bm.verts.new((x, y, -(tb if y == 0 else tf) / 2)) for x, y in pts]
        top = [bm.verts.new((x, y, (tb if y == 0 else tf) / 2)) for x, y in pts]
        bm.faces.new(bot[::-1])
        bm.faces.new(top)
        for i in range(4):
            bm.faces.new((bot[i], bot[(i + 1) % 4], top[(i + 1) % 4], top[i]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        blade = mesh_object(f"Klinge{tag}", bm, blue, (0, 0.0, 0.0235), (math.radians(-12), 0, 0))
        bevel_mod(blade, 0.001, 3)
        ribs = [box(f"Rippe{tag}{i}", (0.05 + 0.012 * i, 0.003, 0.0016), blue, (0, 0.03 + 0.016 * i, 0.0035 - 0.0034 * i), (math.radians(-12), 0, 0), bevel=0.0007, segments=2) for i in range(3)]
        for rb in ribs:
            rb.location.z += 0.0235 - 0.03 * math.sin(math.radians(12)) + 0.0
        g = metaball(f"Faust{tag}", [
            {"type": "CUBE", "co": (0, -0.1, 0), "r": mbr(0.03), "size": (0.036, 0.066, 0.004)},
            {"type": "CAPSULE", "co": (0.076, -0.07, 0), "r": mbr(0.022), "size": (0.03, 1, 1),
             "rot": (0, 0, math.radians(-55))},
        ], shell, resolution=0.003, loc=(0, 0, 0.0245), scale=(1, 1, 0.82))
        cuff = torus(f"Bund{tag}", 0.046, 0.011, fleece, (0, -0.204, 0.0245), (math.pi / 2, 0, 0), seg=(72, 24))
        cuff.scale = (1, 0.42, 1)
        inner = cylinder(f"Futter{tag}", 0.042, 0.006, fleece, (0, -0.201, 0.0245), (math.pi / 2, 0, 0))
        inner.scale = (1, 0.38, 1)
        return [blade, g, cuff, inner] + ribs

    group("Paar1", unit("A"), (-0.02, -0.08, 0), (0, 0, math.radians(-104)))
    group("Paar2", unit("B"), (-0.05, 0.1, 0), (0, 0, math.radians(-76)))
    return {"target": (-0.075, 0.0, 0.02), "S": 0.46, "cam": (-0.2, -0.84, 0.62), "lens": 60, "fstop": 10,
            "bg": (0.8, 0.85, 0.91)}


def zugluftstopper(art: Path) -> dict:
    box("Boden", (4, 4, 0.02), wood("Dielen", planks=True, along="X", scale=0.15), (0, -1.5, -0.01))
    paint = mat("Lack", (0.92, 0.92, 0.91), 0.3, coat=0.25, coat_rough=0.15)
    wallm = plaster("Wand", (0.5, 0.47, 0.42))
    door_w, gap = 0.86, 0.012
    box("Tuerblatt", (door_w, 0.04, 2.0), paint, (0, 0.03, gap + 1.0), bevel=0.002)
    for sx in (-1, 1):
        box(f"Zarge{sx}", (0.07, 0.14, 2.1), paint, (sx * (door_w / 2 + 0.038), 0.03, 1.05), bevel=0.003)
        box(f"Wand{sx}", (1.5, 0.1, 2.5), wallm, (sx * (door_w / 2 + 0.073 + 0.75), 0.07, 1.25))
        box(f"Leiste{sx}", (1.5, 0.014, 0.07), paint, (sx * (door_w / 2 + 0.073 + 0.75), 0.013, 0.035), bevel=0.002)
    linen = fabric("Leinen", (0.11, 0.115, 0.125), weave=700, strength=0.7, sheen=0.35)
    r, L = 0.0175, 0.84
    for y in (0.01 - r - 0.0015, 0.05 + r + 0.0015):
        cylinder("Rolle", r, L, linen, (0, y, r), (0, math.pi / 2, 0), bevel=0.007, verts=72)
    box("Steg", (L - 0.01, 0.085, 0.0022), linen, (0, 0.03, 0.0011))
    sun((0.75, 0.55, -0.42), 1.6, 3.0)
    area((-0.6, -1.2, 0.8), (0, 0, 0.1), 1.2, 25, (1.0, 0.95, 0.9))
    return {"target": (0.2, -0.01, 0.06), "S": 0.5, "cam": (-0.34, -0.56, 0.2), "lens": 32, "fstop": 5,
            "backdrop": False, "lights": False, "view": "agx", "world": (0.82, 0.87, 1.0), "world_strength": 0.3,
            "exposure": -0.3}


def tierhaar(art: Path) -> dict:
    body = plastic("Gehaeuse", (0.84, 0.85, 0.87), 0.3, coat=0.3)
    accent = plastic("Akzent", (0.0, 0.36, 0.40), 0.3)
    dark = plastic("Dunkel", (0.08, 0.085, 0.095), 0.4)
    velvet = mat("Samt", (0.36, 0.03, 0.06), 1.0, sheen=1.0, sheen_rough=0.25, sheen_tint=(1.0, 0.55, 0.55))
    nt, _ = _nodes(velvet)
    bump(velvet, noise(nt, _coords(nt, "Object", (1, 6, 6)), 1500, 2).outputs["Fac"], 0.4, 0.0003)
    W = 0.15
    cylinder("Walze", 0.03, W - 0.012, velvet, (0, 0, 0.03), (0, math.pi / 2, 0), verts=96)
    for sx in (-1, 1):
        cylinder(f"Kappe{sx}", 0.031, 0.008, dark, (sx * (W / 2 - 0.002), 0, 0.03), (0, math.pi / 2, 0), bevel=0.002)
    box("Gehaeuse", (W + 0.012, 0.086, 0.07), body, (0, 0.006, 0.076), bevel=0.022, segments=8)
    box("Klappe", (W - 0.03, 0.008, 0.042), accent, (0, -0.0365, 0.08), bevel=0.003, segments=4)
    box("Taste", (0.02, 0.012, 0.008), dark, (0, 0.0, 0.113), bevel=0.003, segments=3)
    tube_curve("Griff", [(0, 0.03, 0.095), (0, 0.06, 0.17), (0, 0.098, 0.285)], 0.0155, body)
    tube_curve("Griffgummi", [(0, 0.0775, 0.222), (0, 0.098, 0.285)], 0.0168, accent)
    sphere("Griffende", 0.0168, accent, (0, 0.0985, 0.287), 4)
    hair("Haare", (-0.04, -0.09, 0), 90, 0.022, (0.55, 0.36, 0.2), 0.035, 3)
    hair("HaareHell", (0.06, -0.1, 0), 60, 0.018, (0.82, 0.78, 0.7), 0.03, 5)
    return {"target": (0.0, 0.01, 0.12), "S": 0.36, "cam": (-0.42, -0.6, 0.26), "lens": 70, "fstop": 9}


def packwuerfel(art: Path) -> dict:
    navy = fabric("Navy", (0.03, 0.05, 0.11), weave=1100, strength=0.35, sheen=0.55)
    netz = mat("Netz", (0.035, 0.04, 0.05), 0.75)
    nt, _ = _nodes(netz)
    v = _coords(nt)
    bump(netz, math_node(nt, "MULTIPLY", wave(nt, v, 420, "X", profile="SAW").outputs["Fac"],
                         wave(nt, v, 420, "Y", profile="SAW").outputs["Fac"]), 0.6, 0.0006)
    tape = fabric("Band", (0.15, 0.16, 0.18), weave=1700, strength=0.3)
    orange = plastic("Zipper", (0.95, 0.42, 0.06), 0.3)

    def cube(tag, w, d, h, loc, rz, window=True):
        parts = [box(f"Wuerfel{tag}", (w, d, h), navy, (0, 0, h / 2), bevel=min(0.02, h * 0.3), segments=6)]
        if window:
            parts.append(rounded_rect(f"Netz{tag}", w - 0.055, d - 0.055, 0.014, netz, (0, 0, h + 0.0005), uv=False))
        parts.append(box(f"Reiss{tag}", (w + 0.003, d + 0.003, 0.008), tape, (0, 0, h - min(0.016, h * 0.4)),
                         bevel=0.004, segments=4))
        parts.append(box(f"Zug{tag}", (0.024, 0.007, 0.0045), orange, (w / 2 - 0.045, -d / 2 - 0.004,
                                                                       h - min(0.016, h * 0.4)), bevel=0.0018))
        if h > 0.05:
            parts.append(box(f"Schlaufe{tag}", (0.055, 0.006, 0.016), tape, (-w / 4, -d / 2 - 0.0015, h * 0.5),
                             bevel=0.002))
        return group(f"G{tag}", parts, loc, (0, 0, math.radians(rz)))

    cube("L", 0.38, 0.28, 0.11, (0.03, 0.08, 0), 4)
    cube("M", 0.33, 0.24, 0.10, (0.04, 0.09, 0.11), -5)
    cube("S", 0.26, 0.19, 0.085, (0.03, 0.085, 0.21), 7)
    cube("XS", 0.21, 0.15, 0.075, (-0.27, -0.16, 0), -16)
    cube("Flach1", 0.31, 0.22, 0.026, (0.3, -0.2, 0), 18, window=False)
    cube("Flach2", 0.25, 0.17, 0.022, (0.3, -0.2, 0.026), 8, window=False)
    return {"target": (0.0, -0.02, 0.12), "S": 0.75, "cam": (-0.62, -1.2, 0.72), "lens": 55, "fstop": 11}


def baender(art: Path) -> dict:
    colors = [("Salbei", (0.30, 0.41, 0.33), 0.106), ("Rose", (0.72, 0.38, 0.38), 0.116),
              ("Anthrazit", (0.1, 0.105, 0.115), 0.126)]
    W, t = 0.076, 0.0065
    for i, (name, c, R) in enumerate(colors):
        ring = band_ring(name, R, W, t, fabric(name, c, weave=800, strength=0.55, sheen=0.6))
        ring.rotation_euler = (0, math.pi / 2, 0)
        ring.scale = (0.86, 1, 1)
        ring.location = (-0.12 + i * 0.12, 0.06 - i * 0.07, 0)
        ring.location.z -= lowest_z([ring])
        lab = box(f"Etikett{i}", (0.03, 0.002, 0.016), mat(f"Etikett{i}", (0.9, 0.88, 0.84), 0.8),
                  (ring.location.x - 0.005, ring.location.y - R - t / 2 - 0.0005, ring.location.z), bevel=0.0007)
        lab.location.z = ring.location.z + 0.002
    return {"target": (0.0, 0.0, 0.1), "S": 0.5, "cam": (-0.5, -0.82, 0.42), "lens": 60, "fstop": 11}


def laptop(art: Path) -> dict:
    alu = brushed("Alu", (0.8, 0.81, 0.83), 0.27, "Y")
    pad = rubber("Pad", (0.08, 0.08, 0.09), 0.7)
    th, bw = 0.008, 0.024
    for sx in (-1, 1):
        x = sx * 0.105
        for nm, a, b in (("Fuss", (x, -0.13, th / 2), (x, 0.11, th / 2)), ("Stuetze", (x, 0.1, th), (x, 0.065, 0.168)),
                         ("Auflage", (x, 0.07, 0.17), (x, -0.155, 0.083)), ("Strebe", (x, -0.115, th), (x, -0.035, 0.124))):
            bar(f"{nm}{sx}", a, b, alu, bw, th)
        bar(f"Haken{sx}", (x, -0.156, 0.08), (x, -0.161, 0.1), alu, bw, th * 0.8)
        for yy, zz in ((0.0, 0.142), (-0.11, 0.1)):
            p = box(f"Pad{sx}{yy}", (bw * 0.8, 0.05, 0.002), pad, (x, yy, zz + th / 2 + 0.001), bevel=0.0008)
            p.rotation_euler = (math.atan2(0.087, 0.225), 0, 0)
        for yy, zz in ((0.0675, 0.168), (-0.034, 0.124)):
            cylinder(f"Gelenk{sx}{yy}", 0.0065, bw + 0.004, alu, (x, yy, zz), (0, math.pi / 2, 0), bevel=0.001)
    box("Querstrebe", (0.21 + bw, 0.018, th), alu, (0, 0.105, th / 2), bevel=0.002)
    box("Querstrebe2", (0.21 + bw, 0.012, th), alu, (0, 0.067, 0.168), bevel=0.002)
    # Laptop in eigenem Rahmen, dann aufgelegt
    silver = brushed("Gehaeuse", (0.86, 0.87, 0.89), 0.3, "X")
    keys = mat("Tasten", (0.03, 0.03, 0.035), 0.55)
    nt, b = _nodes(keys)
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Mortar Size"].default_value = 0.0012
    br.inputs["Brick Width"].default_value = 0.0175
    br.inputs["Row Height"].default_value = 0.0175
    br.inputs["Color1"].default_value = (0.035, 0.035, 0.04, 1)
    br.inputs["Color2"].default_value = (0.03, 0.03, 0.035, 1)
    br.inputs["Mortar"].default_value = (0.006, 0.006, 0.007, 1)
    nt.links.new(_coords(nt, "Object"), br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], b.inputs["Base Color"])
    bump(keys, br.outputs["Fac"], 0.6, 0.0006)
    parts = [box("Unterteil", (0.31, 0.215, 0.015), silver, (0, 0, 0), bevel=0.004, segments=4),
             rounded_rect("Tastatur", 0.27, 0.098, 0.004, keys, (0, 0.035, 0.0076), uv=False),
             rounded_rect("Trackpad", 0.115, 0.068, 0.006, mat("Pad", (0.74, 0.75, 0.77), 0.35, 0.8),
                          (0, -0.063, 0.0076), uv=False)]
    hinge = link(bpy.data.objects.new("Scharnier", None))
    hinge.location = (0, 0.1075, 0.0075)
    lid = [box("Deckel", (0.31, 0.215, 0.006), silver, (0, -0.1075, 0.003), bevel=0.003, segments=3),
           rounded_rect("Rand", 0.302, 0.207, 0.006, mat("Rahmen", (0.01, 0.01, 0.012), 0.08, spec=0.6),
                        (0, -0.1075, -0.0001), (math.pi, 0, 0), uv=False)]
    scr = art / "screen_laptop.png"
    if scr.exists():
        lid.append(rounded_rect("Display", 0.286, 0.178, 0.002,
                                image_mat("Bild", scr, emission=1.4, base_dark=True), (0, -0.1105, -0.0004),
                                (math.pi, 0, 0)))
    for o in lid:
        o.parent = hinge
    hinge.rotation_euler = (math.radians(-112), 0, 0)
    beta = math.atan2(0.087, 0.225)
    n = Vector((0, -math.sin(beta), math.cos(beta)))
    mid = Vector((0, -0.04, 0.1265)) + n * (th / 2 + 0.002 + 0.0075)
    group("Laptop", parts + [hinge], mid, (beta, 0, 0))
    return {"target": (0.0, 0.0, 0.2), "S": 0.53, "cam": (-0.44, -0.66, 0.3), "lens": 58, "fstop": 11}


def frostschutz(art: Path) -> dict:
    silver = mat("Silber", (0.78, 0.8, 0.83), 0.3, 0.9)
    nt, _ = _nodes(silver)
    v = _coords(nt, "Object", (1, 1, 1), (0, 0, math.radians(45)))
    q = math_node(nt, "MULTIPLY", wave(nt, v, 24, "X").outputs["Fac"], wave(nt, v, 24, "Y").outputs["Fac"])
    bump(silver, q, 0.5, 0.003)
    black = fabric("Kante", (0.025, 0.025, 0.03), weave=1200, strength=0.3)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=150, y_segments=100, size=0.5)
    for vv in bm.verts:
        vv.co.x *= 1.5
    sheet = mesh_object("Abdeckung", bm, silver, (0, 0, 0.0062))
    _finish(sheet)
    displace(sheet, 0.012, 0.22, midlevel=0.0)
    rounded_rect("Rand", 1.53, 1.03, 0.04, black, (0, 0, 0.005), thickness=0.005, uv=False)
    for sx in (-1, 1):
        pts = [(0, -0.33), (0.26, -0.24), (0.26, 0.24), (0, 0.33)]
        outline(f"Lasche{sx}", [(sx * (0.76 + x), y) for x, y in pts][:: sx], 0.003, black, (0, 0, 0.0))
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        box(f"Magnet{sx}{sy}", (0.05, 0.03, 0.004), black, (sx * 0.62, sy * 0.43, 0.012), bevel=0.0015)
    box("Tasche", (0.3, 0.22, 0.035), black, (0.62, -0.72, 0.0175), (0, 0, math.radians(-12)), bevel=0.012)
    return {"target": (0.1, -0.08, 0.0), "S": 2.45, "cam": (-0.36, -1.6, 1.1), "lens": 36, "fstop": 14,
            "bg": (0.55, 0.6, 0.66)}


def frostschutz_auto(art: Path) -> dict:
    """Die Abdeckung auf der Windschutzscheibe eines Autos an einem frostigen Morgen."""
    paint = mat("Lack", (0.3, 0.01, 0.02), 0.2, 0.4, coat=1.0, coat_rough=0.03)
    glass = mat("Scheibe", (0.012, 0.014, 0.018), 0.03, spec=0.8)
    BW = 0.9
    # Stationen entlang des Autos: (y, Höhe, halbe Breite oben, Wölbung)
    st = [(-2.05, 0.68, 0.8, 0.03), (-1.97, 0.8, 0.84, 0.04), (-1.6, 0.88, 0.87, 0.05), (-1.15, 0.93, 0.88, 0.05),
          (-0.86, 0.955, 0.88, 0.05), (-0.62, 1.08, 0.83, 0.045), (-0.36, 1.22, 0.77, 0.04), (-0.1, 1.35, 0.72, 0.035),
          (0.06, 1.43, 0.69, 0.03), (0.3, 1.47, 0.68, 0.03), (1.4, 1.48, 0.68, 0.03)]
    nv = 24
    bm = bmesh.new()
    rows = []
    for y, z, hw, crown in st:
        cabin = y > -0.87
        side = 0.98 if cabin else z - 0.1
        pts = [(-BW, 0.4), (-BW, side), (-hw * 1.02, z - crown - 0.02)]
        pts += [((-1 + 2 * i / nv) * hw, z - crown * (-1 + 2 * i / nv) ** 2) for i in range(nv + 1)]
        pts += [(hw * 1.02, z - crown - 0.02), (BW, side), (BW, 0.4)]
        rows.append([bm.verts.new((x, y, zz)) for x, zz in pts])
    n = len(rows[0])
    for k in range(len(rows) - 1):
        y0, y1 = st[k][0], st[k + 1][0]
        wind = -0.87 < (y0 + y1) / 2 < 0.07
        cabin = (y0 + y1) / 2 > -0.87
        for j in range(n - 1):
            f = bm.faces.new((rows[k][j], rows[k][j + 1], rows[k + 1][j + 1], rows[k + 1][j]))
            v = -1 + 2 * ((j + 0.5) - 3) / nv
            top = 3 <= j < 3 + nv
            f.material_index = 1 if ((top and wind and abs(v) < 0.86) or (cabin and j in (1, n - 3))) else 0
    bm.faces.new(rows[0][::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    car = mesh_object("Auto", bm, paint)
    car.data.materials.append(glass)
    subdivide(car, 2)
    _finish(car)

    def at(y: float, v: float, lift: float):
        for (ya, za, ha, ca), (yb, zb, hb, cb) in pairwise(st):
            if ya <= y <= yb:
                t = (y - ya) / (yb - ya)
                z, hw, crown = za + (zb - za) * t, ha + (hb - ha) * t, ca + (cb - ca) * t
                return Vector((v * hw, y, z - crown * v * v + lift))
        raise ValueError(y)

    silver = mat("Silber", (0.78, 0.8, 0.83), 0.3, 0.9)
    ntt, _ = _nodes(silver)
    qv = _coords(ntt, "Object", (1, 1, 1), (0, 0, math.radians(45)))
    bump(silver, math_node(ntt, "MULTIPLY", wave(ntt, qv, 24, "X").outputs["Fac"], wave(ntt, qv, 24, "Y").outputs["Fac"]),
         0.5, 0.003)
    black = fabric("Kante", (0.025, 0.025, 0.03), weave=1200, strength=0.3)
    for name_, m_, vmax, y0, y1, lift in (("Rand", black, 0.995, -0.85, 0.05, 0.012),
                                          ("Abdeckung", silver, 0.965, -0.83, 0.03, 0.016)):
        g = bmesh.new()
        grid = []
        for i in range(41):
            y = y0 + (y1 - y0) * i / 40
            grid.append([g.verts.new(at(y, -vmax + 2 * vmax * j / 30, lift)) for j in range(31)])
        for i in range(40):
            for j in range(30):
                g.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
        sheet = mesh_object(name_, g, m_)
        _finish(sheet)
        displace(sheet, 0.006, 0.12, midlevel=0.0)
    for sx in (-1, 1):  # Laschen, die in der Tür eingeklemmt werden
        a0, a1 = at(-0.6, sx * 0.995, 0.012), at(-0.2, sx * 0.995, 0.012)
        flap = bmesh.new()
        vs = [flap.verts.new(a0), flap.verts.new(a1), flap.verts.new((sx * (BW + 0.008), -0.25, 1.0)),
              flap.verts.new((sx * (BW + 0.008), -0.55, 1.0))]
        flap.faces.new(vs if sx > 0 else vs[::-1])
        mesh_object(f"Lasche{sx}", flap, black)
        box(f"Spiegel{sx}", (0.2, 0.1, 0.12), paint, (sx * (BW + 0.08), -0.74, 1.06), bevel=0.035, segments=5)
        box(f"Spiegelfuss{sx}", (0.1, 0.06, 0.05), mat("Schwarz", (0.02, 0.02, 0.022), 0.5), (sx * (BW + 0.01), -0.76, 1.02),
            bevel=0.01)
        box(f"Scheinwerfer{sx}", (0.36, 0.06, 0.1), mat("Lampe", (0.9, 0.92, 0.95), 0.05, 1.0), (sx * 0.58, -2.0, 0.74),
            (math.radians(-20), 0, 0), bevel=0.03, segments=4)
        box(f"Wischer{sx}", (0.55, 0.012, 0.012), mat("Gummi", (0.02, 0.02, 0.02), 0.6), (sx * 0.3, -0.84, 0.985),
            (0, 0, sx * math.radians(-6)), bevel=0.004)
    box("Grill", (0.7, 0.06, 0.12), mat("Grill", (0.02, 0.02, 0.025), 0.35), (0, -2.06, 0.6), bevel=0.03)
    snow = mat("Schnee", (0.9, 0.92, 0.95), 0.75, sss=0.2, sss_radius=(0.05, 0.05, 0.06), sss_scale=0.05)
    ntt, _ = _nodes(snow)
    bump(snow, noise(ntt, _coords(ntt), 6, 8, 0.7).outputs["Fac"], 0.4, 0.02)
    box("Boden", (30, 30, 0.02), snow, (0, 0, -0.01))
    sun((0.55, -0.55, -0.35), 2.6, 2.0, (1.0, 0.86, 0.7))
    area((-3.0, -4.0, 3.0), (0, -0.6, 1.0), 3.0, 900, (0.9, 0.94, 1.0))
    world_gradient((0.92, 0.88, 0.84), (0.3, 0.45, 0.72), 1.0)
    return {"target": (0.08, -0.62, 1.08), "S": 1.0, "cam": (-2.05, -2.95, 1.5), "lens": 40, "fstop": 0,
            "backdrop": False, "lights": False, "view": "agx", "world": None, "exposure": -0.3}


def fellhandschuh(art: Path) -> dict:
    shell = fabric("Netzstoff", (0.02, 0.022, 0.026), weave=520, strength=0.45, sheen=0.2)
    sil = rubber("Silikon", (0.07, 0.25, 0.6), 0.45)
    strap = fabric("Klett", (0.035, 0.037, 0.042), weave=1500, strength=0.6)
    st = 12.0

    def glove(tag: str, nubs: bool):
        E = []
        E.append({"type": "CAPSULE", "co": (0, 0.0, 0), "r": mbr(0.044), "size": (0.012, 1, 1)})
        E.append({"type": "CAPSULE", "co": (0, 0.03, 0), "r": mbr(0.04), "size": (0.012, 1, 1)})
        for fx, fy, half, rad, ang in ((-0.033, 0.06, 0.029, 0.0094, 7), (-0.011, 0.066, 0.034, 0.0098, 2),
                                       (0.0115, 0.064, 0.032, 0.0097, -3), (0.032, 0.056, 0.024, 0.009, -9)):
            a = math.radians(90 + ang)
            E.append({"type": "CAPSULE", "co": (fx + math.cos(a) * half, fy + math.sin(a) * half, 0),
                      "r": mbr(rad, st), "stiff": st, "size": (half, 1, 1), "rot": (0, 0, a)})
        E.append({"type": "CAPSULE", "co": (-0.058, 0.012, 0), "r": mbr(0.0118, st), "stiff": st,
                  "size": (0.022, 1, 1), "rot": (0, 0, math.radians(128))})
        E.append({"type": "CAPSULE", "co": (0, -0.06, 0), "r": mbr(0.034, st), "stiff": st, "size": (0.012, 1, 1)})
        E.append({"type": "CAPSULE", "co": (0, -0.085, 0), "r": mbr(0.033, st), "stiff": st, "size": (0.011, 1, 1)})
        g = metaball(f"Hand{tag}", E, shell, resolution=0.0014, scale=(1, 1, 0.34))
        g = to_mesh(g, f"Handschuh{tag}")
        sm = g.modifiers.new("Glaetten", "SMOOTH")
        sm.factor = 0.8
        sm.iterations = 12
        g.location.z -= lowest_z([g])
        bpy.context.view_layer.update()
        parts = [g]
        deps = bpy.context.evaluated_depsgraph_get()
        ev = g.evaluated_get(deps)
        me = ev.to_mesh()
        verts = [g.matrix_world @ vv.co for vv in me.vertices]
        tree = BVHTree.FromPolygons(verts, [list(pp.vertices) for pp in me.polygons])
        ev.to_mesh_clear()
        # Klettriemen: folgt der gewölbten Oberfläche am Handgelenk
        rb = bmesh.new()
        rows = []
        for i in range(31):
            x = -0.065 + 0.13 * i / 30
            row = []
            for y in (-0.081, -0.059):
                hit, normal, _, _ = tree.ray_cast(Vector((x, y, 0.3)), Vector((0, 0, -1)))
                if hit is None:
                    row = []
                    break
                row.append(rb.verts.new(hit + normal * 0.0012))
            if row:
                rows.append(row)
        for r0, r1 in pairwise(rows):
            rb.faces.new((r0[0], r1[0], r1[1], r0[1]))
        band = mesh_object(f"Riemen{tag}", rb, strap)
        sol = band.modifiers.new("Dicke", "SOLIDIFY")
        sol.thickness = 0.0022
        _finish(band)
        parts.append(band)
        if nubs:
            nb = bmesh.new()
            bmesh.ops.create_cone(nb, cap_ends=True, segments=12, radius1=0.0027, radius2=0.0022, depth=0.0036)
            nm = bpy.data.meshes.new(f"Noppe{tag}")
            nb.to_mesh(nm)
            nb.free()
            for pp in nm.polygons:
                pp.use_smooth = True
            nm.materials.append(sil)
            step = 0.0082
            k = 0
            for iy in range(40):
                y = -0.045 + iy * step * 0.87
                for ix in range(-12, 13):
                    x = ix * step + (step / 2 if iy % 2 else 0)
                    hit, normal, _, _ = tree.ray_cast(Vector((x, y, 0.3)), Vector((0, 0, -1)))
                    if hit is None or normal.z < 0.8:
                        continue
                    # nicht am Rand: rundherum muss Handschuh sein
                    if any(tree.ray_cast(Vector((x + dx, y + dy, 0.3)), Vector((0, 0, -1)))[0] is None
                           for dx, dy in ((0.0045, 0), (-0.0045, 0), (0, 0.0045), (0, -0.0045))):
                        continue
                    ob = link(bpy.data.objects.new(f"N{tag}{k}", nm))
                    ob.location = hit + normal * 0.0012
                    ob.rotation_euler = normal.to_track_quat("Z", "Y").to_euler()
                    k += 1
                    parts.append(ob)
        return parts

    group("HandA", glove("A", True), (0.035, -0.01, 0.0), (0, 0, math.radians(14)))
    back = glove("B", False)
    gb = group("HandB", back, (-0.09, 0.06, 0.0), (0, 0, math.radians(-20)))
    gb.location.z = 0.0
    return {"target": (-0.02, 0.02, 0.01), "S": 0.36, "cam": (-0.18, -0.52, 0.48), "lens": 62, "fstop": 10}


def wandhaken(art: Path) -> dict:
    tile = mat("Fliese", (0.62, 0.68, 0.63), 0.12, coat=0.3, coat_rough=0.05)
    nt, b = _nodes(tile)
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.5
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Mortar Size"].default_value = 0.0025
    br.inputs["Mortar Smooth"].default_value = 0.4
    br.inputs["Brick Width"].default_value = 0.15
    br.inputs["Row Height"].default_value = 0.075
    br.inputs["Color1"].default_value = (0.6, 0.67, 0.62, 1)
    br.inputs["Color2"].default_value = (0.57, 0.64, 0.59, 1)
    br.inputs["Mortar"].default_value = (0.85, 0.85, 0.83, 1)
    nt.links.new(_coords(nt, "Object", (1, 1, 1), (math.pi / 2, 0, 0)), br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], b.inputs["Base Color"])
    bump(tile, br.outputs["Fac"], 0.5, 0.0015)
    box("Wand", (1.6, 0.02, 1.0), tile, (0, 0.01, 0.5))
    box("Ablage", (1.6, 0.6, 0.03), wood("Arbeitsplatte", (0.7, 0.55, 0.38), (0.52, 0.38, 0.24), along="X"),
        (0, -0.3, 0.015))
    acrylic = clear_plastic("Acryl", (0.97, 0.985, 1.0), 0.03)
    foam = mat("Klebepad", (0.93, 0.93, 0.92), 0.9)
    z0 = 0.42
    for i, x in enumerate((-0.13, 0.0, 0.13)):
        box(f"Pad{i}", (0.03, 0.0012, 0.04), foam, (x, -0.0006, z0), bevel=0.0004)
        see_through(box(f"Platte{i}", (0.034, 0.0035, 0.044), acrylic, (x, -0.003, z0), bevel=0.0015, segments=4),
                    tube_curve(f"Haken{i}", [(x, -0.004, z0 - 0.004), (x, -0.012, z0 - 0.0105),
                                             (x, -0.022, z0 - 0.0115), (x, -0.029, z0 - 0.004),
                                             (x, -0.0305, z0 + 0.007)], 0.0032, acrylic))
    zc = z0 - 0.0115 - 0.0032
    # Schlüsselbund am linken Haken
    steel = mat("Stahl", (0.75, 0.76, 0.78), 0.25, 1.0)
    brass = mat("Messing", (0.83, 0.62, 0.33), 0.28, 1.0)
    torus("Ring", 0.012, 0.0011, steel, (-0.13, -0.021, zc - 0.0108), (0, math.pi / 2, 0), seg=(48, 10))
    key = [(-0.0125, 0.0), (-0.0095, 0.0085), (0.0, 0.0125), (0.0095, 0.0085), (0.0125, 0.0), (0.0095, -0.008),
           (0.004, -0.011), (0.004, -0.05), (0.0015, -0.053), (-0.004, -0.053), (-0.004, -0.047), (-0.0015, -0.044),
           (-0.004, -0.041), (-0.004, -0.035), (-0.0015, -0.032), (-0.004, -0.029), (-0.004, -0.011),
           (-0.0095, -0.008)]
    for j, (m_, dx, rz) in enumerate(((brass, -0.004, 8), (steel, 0.004, -10))):
        outline(f"Schluessel{j}", key, 0.002, m_, (-0.13 + dx, -0.022 + j * 0.003, zc - 0.0108 - 0.0225),
                (math.pi / 2, math.radians(rz), 0), bevel=0.0006)
    # Kochlöffel am mittleren Haken
    torus("Schlaufe", 0.016, 0.0022, mat("Leder", (0.35, 0.2, 0.1), 0.6), (0.0, -0.021, zc - 0.0138),
                 (0, math.pi / 2, 0), seg=(48, 12))
    lofel = [(-0.009, -0.02), (-0.0065, -0.0125), (0.0, -0.011), (0.0065, -0.0125), (0.009, -0.02), (0.0095, -0.172)]
    lofel += [(0.031 * math.cos(a), -0.215 + 0.045 * math.sin(a)) for a in
              [math.pi / 2 - 0.75 + i * (-(2 * math.pi - 1.5)) / 30 for i in range(31)]]
    lofel += [(-0.0095, -0.172)]
    outline("Kochloeffel", lofel, 0.007, wood("Buche", (0.78, 0.6, 0.42), (0.62, 0.45, 0.3), along="Y", scale=0.3),
            (0.0, -0.018, zc - 0.03 + 0.012), (math.pi / 2, 0, 0), bevel=0.0025)
    return {"target": (0.0, -0.01, 0.36), "S": 0.42, "cam": (-0.3, -0.62, 0.12), "lens": 62, "fstop": 9,
            "backdrop": False, "world": (0.92, 0.94, 0.96), "world_strength": 0.6}


def rollbeutel(art: Path) -> dict:
    film = mat("Folie", (0.97, 0.98, 1.0), 0.1, trans=1.0, ior=1.34, spec=0.5)
    blue = plastic("Zip", (0.08, 0.3, 0.7), 0.3)
    valve = mat("Ventil", (0.92, 0.93, 0.95), 0.35, trans=0.4)

    def bag(tag, colors, loc, rz):
        parts = []
        z = 0.004
        for i, c in enumerate(colors):
            k = knit(f"Strick{tag}{i}", c, rib=230, strength=0.45, direction="X")
            parts.append(box(f"Kleid{tag}{i}", (0.33 - i * 0.012, 0.24 - i * 0.01, 0.017), k,
                             (i * 0.005 - 0.004, i * 0.004, z + 0.0085), bevel=0.0075, segments=4))
            z += 0.0172
        top = z + 0.006
        b = box(f"Beutel{tag}", (0.4, 0.3, top), film, (0.0, 0.0, top / 2), bevel=0.028, segments=8)
        subdivide(b, 1)
        displace(b, 0.0035, 0.05)
        see_through(b)
        parts.append(b)
        for dx in (0.0, 0.007):
            parts.append(cylinder(f"Zip{tag}{dx}", 0.0018, 0.29, blue, (0.165 + dx, 0, top + 0.0012),
                                  (math.pi / 2, 0, 0)))
        for vy in (-0.065, 0.065):
            parts.append(cylinder(f"Ventil{tag}{vy}", 0.012, 0.004, valve, (-0.165, vy, top + 0.0015), bevel=0.0012))
        return group(f"Beutel{tag}", parts, loc, (0, 0, math.radians(rz)))

    bag("A", [(0.45, 0.46, 0.48), (0.05, 0.08, 0.16), (0.72, 0.64, 0.52)], (0.04, -0.03, 0), 12)
    bag("B", [(0.3, 0.34, 0.22), (0.86, 0.83, 0.76)], (-0.1, 0.22, 0), -8)
    return {"target": (0.0, 0.05, 0.03), "S": 0.6, "cam": (-0.35, -0.85, 0.75), "lens": 55, "fstop": 11}


def handystaender(art: Path) -> dict:
    alu = brushed("Alu", (0.3, 0.31, 0.34), 0.3, "X")
    pad = rubber("Pad", (0.06, 0.06, 0.07), 0.7)
    base = rounded_rect("Fuss", 0.078, 0.092, 0.014, alu, (0, 0, 0.0075), thickness=0.0075, uv=False)
    bevel_mod(base, 0.0016, 3, angle=40)
    tilt = math.radians(68)
    h1, h2 = Vector((0, 0.03, 0.013)), Vector((0, 0.011, 0.108))
    cylinder("Gelenk1", 0.0078, 0.05, alu, h1, (0, math.pi / 2, 0), bevel=0.0012)
    bar("Arm", h1, h2, alu, 0.042, 0.0075)
    cylinder("Gelenk2", 0.0072, 0.046, alu, h2, (0, math.pi / 2, 0), bevel=0.0012)
    up = Vector((0, math.cos(tilt), math.sin(tilt)))
    n = Vector((0, -math.sin(tilt), math.cos(tilt)))
    plen = 0.075
    pmid = h2 - up * (plen / 2) + n * 0.004
    box("Halter", (0.05, plen, 0.006), alu, pmid, (tilt, 0, 0), bevel=0.0018)
    bottom = h2 - up * plen + n * 0.004
    box("Lippe", (0.05, 0.006, 0.016), alu, bottom + n * 0.008, (tilt, 0, 0), bevel=0.0018)
    for k in (0.25, 0.7):
        box(f"Pad{k}", (0.036, 0.008, 0.0015), pad, h2 - up * (plen * k) + n * 0.0078, (tilt, 0, 0), bevel=0.0006)
    box("PadLippe", (0.044, 0.0015, 0.006), pad, bottom + n * 0.012 + up * 0.0035, (tilt, 0, 0), bevel=0.0005)
    ph = phone("S", art / "wallpaper_jungle.png", (0.15, 0.16, 0.18), 1.5)
    contact = bottom + up * 0.0035 + n * (0.003 + 0.0078 + 0.0008)
    group("Handy", ph, contact + up * (0.1475 / 2), (tilt, 0, 0))
    return {"target": (0.0, 0.0, 0.085), "S": 0.26, "cam": (-0.25, -0.42, 0.13), "lens": 70, "fstop": 8}


def wallpaper(art: Path) -> dict:
    stone = mat("Stein", (0.075, 0.078, 0.085), 0.65)
    nt, b = _nodes(stone)
    v = _coords(nt)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (0.05, 0.052, 0.058, 1)
    mix.inputs["B"].default_value = (0.11, 0.112, 0.12, 1)
    nt.links.new(noise(nt, v, 9, 8, 0.7).outputs["Fac"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    bump(stone, noise(nt, v, 400, 6).outputs["Fac"], 0.15, 0.0004)
    box("Tisch", (2.0, 2.0, 0.03), stone, (0, 0, -0.015))
    area((-0.5, -0.05, 0.25), (0, 0, 0), 0.4, 6, (1.0, 0.95, 0.88))
    area((0.55, 0.1, 0.2), (0, 0, 0), 0.5, 2.5, (0.9, 0.95, 1.0))
    area((0.0, 0.6, 0.18), (0, 0, 0), 0.4, 3, (1, 1, 1))
    picks = ["medieval", "iceage", "jungle"]
    for i, (w, x, y, rz) in enumerate(zip(picks, (-0.088, 0.0, 0.088), (0.004, 0.018, 0.0), (9, 0, -9))):
        ph = phone(str(i), art / f"wallpaper_{w}.png", (0.07, 0.075, 0.085), 1.35)
        group(f"Handy{i}", ph, (x, y, 0.0078), (0, 0, math.radians(rz)))
    return {"target": (0.0, 0.012, 0.0), "S": 0.3, "cam": (0.0, -0.26, 0.4), "lens": 50, "fstop": 11,
            "backdrop": False, "lights": False, "world": (0.9, 0.9, 0.92), "world_strength": 0.08}


def poster_room(art: Path, world_key: str) -> dict:
    wallm = plaster("Wand", (0.78, 0.76, 0.72))
    box("Wand", (4.0, 0.1, 2.8), wallm, (0, 0.05, 1.4))
    box("Boden", (4.0, 4.0, 0.02), wood("Parkett", (0.66, 0.5, 0.34), (0.48, 0.34, 0.21), planks=True, scale=0.15),
        (0, -1.9, -0.01))
    oak = wood("Eiche", (0.7, 0.54, 0.37), (0.55, 0.4, 0.26), along="X", rough=0.5, scale=0.25)
    metal = mat("Schwarz", (0.02, 0.02, 0.022), 0.4, 0.8)
    W, D, H, leg = 1.5, 0.42, 0.56, 0.16
    box("Korpus", (W, D - 0.01, H - leg), oak, (0, -D / 2 + 0.005, leg + (H - leg) / 2), bevel=0.003)
    for i in range(3):
        box(f"Front{i}", (W / 3 - 0.006, 0.012, H - leg - 0.03), oak, (-W / 3 + i * W / 3, -D + 0.004, leg + (H - leg) / 2),
            bevel=0.002)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cylinder(f"Bein{sx}{sy}", 0.011, leg, metal, (sx * (W / 2 - 0.06), -D / 2 + sy * (D / 2 - 0.06), leg / 2),
                     radius2=0.008)
    # Poster A3 im schmalen Eichenrahmen
    pw, ph, fb, fd = 0.297, 0.42, 0.016, 0.022
    cz = 1.06
    poster = art / f"poster_{world_key}.png"
    rounded_rect("Poster", pw, ph, 0.0001, image_mat("Druck", poster, rough=0.7), (0, -0.003, cz), (math.pi / 2, 0, 0))
    frame = wood("Rahmen", (0.76, 0.6, 0.42), (0.62, 0.46, 0.3), along="X", scale=0.3, rough=0.55)
    for nm, sz, loc in (("Oben", (pw + 2 * fb, fd, fb), (0, -fd / 2, cz + ph / 2 + fb / 2)),
                        ("Unten", (pw + 2 * fb, fd, fb), (0, -fd / 2, cz - ph / 2 - fb / 2)),
                        ("Links", (fb, fd, ph), (-pw / 2 - fb / 2, -fd / 2, cz)),
                        ("Rechts", (fb, fd, ph), (pw / 2 + fb / 2, -fd / 2, cz))):
        box(f"Rahmen{nm}", sz, frame, loc, bevel=0.0015, segments=2)
    # Deko: Vase mit Zweigen, Bücher, Kerze
    ceramic = mat("Keramik", (0.86, 0.83, 0.77), 0.55, sss=0.05, sss_radius=(0.01, 0.008, 0.006), sss_scale=0.02)
    nt, _ = _nodes(ceramic)
    bump(ceramic, noise(nt, _coords(nt), 180, 6).outputs["Fac"], 0.15, 0.0008)
    prof = [(0.0, 0.0), (0.055, 0.0), (0.07, 0.03), (0.078, 0.09), (0.066, 0.16), (0.04, 0.205), (0.032, 0.235),
            (0.036, 0.25), (0.03, 0.25), (0.026, 0.235), (0.024, 0.2)]
    vx, vy = -0.4, -0.2
    lathe("Vase", prof, ceramic, 72, (vx, vy, H))
    twig = mat("Zweig", (0.25, 0.2, 0.15), 0.7)
    leafm = mat("Blatt", (0.32, 0.42, 0.3), 0.55, sss=0.1, sss_radius=(0.01, 0.02, 0.005), sss_scale=0.01)
    rnd = random.Random(7)
    for k, (ang, lean, ln) in enumerate(((2.0, 0.3, 0.44), (2.9, 0.4, 0.36), (3.8, 0.24, 0.5))):
        dx, dy = math.cos(ang) * lean, math.sin(ang) * lean
        pts = [(vx, vy, H + 0.18), (vx + dx * 0.25, vy + dy * 0.15, H + 0.18 + ln * 0.45),
               (vx + dx * 0.7, vy + dy * 0.35, H + 0.18 + ln * 0.85), (vx + dx, vy + dy * 0.45, H + 0.18 + ln)]
        tube_curve(f"Zweig{k}", pts, 0.0022, twig)
        for j in range(16):
            t = 0.25 + 0.75 * j / 15
            # Punkt auf dem Polygonzug (genügt für die Blattposition)
            seg = min(int(t * 3), 2)
            u = t * 3 - seg
            p = Vector(pts[seg]).lerp(Vector(pts[seg + 1]), u)
            side = 1 if j % 2 else -1
            lf = sphere(f"Blatt{k}{j}", 1.0, leafm, p, 2, (0.024, 0.0065, 0.0012))
            lf.rotation_euler = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.3, 0.3), ang + side * 1.0 + rnd.uniform(-0.3, 0.3))
            lf.location += Vector((math.cos(lf.rotation_euler.z), math.sin(lf.rotation_euler.z), 0)) * 0.018
    zb = H
    for i, (w_, d_, h_, c, rz) in enumerate(((0.24, 0.17, 0.028, (0.62, 0.3, 0.2), 3), (0.22, 0.16, 0.034, (0.78, 0.7, 0.56), -4),
                                             (0.2, 0.14, 0.022, (0.22, 0.27, 0.32), 6))):
        box(f"Buch{i}", (w_, d_, h_), fabric(f"Einband{i}", c, weave=700, strength=0.2), (0.34, -0.21, zb + h_ / 2),
            (0, 0, math.radians(rz)), bevel=0.003)
        zb += h_
    cylinder("Kerze", 0.028, 0.09, mat("Wachs", (0.92, 0.9, 0.85), 0.5, sss=0.3, sss_radius=(0.02, 0.015, 0.01),
                                         sss_scale=0.02), (0.34, -0.21, zb + 0.045), bevel=0.003)
    # Pflanze rechts auf dem Boden
    lathe("Topf", [(0.0, 0.0), (0.1, 0.0), (0.125, 0.26), (0.118, 0.26), (0.095, 0.02)],
                mat("Topf", (0.9, 0.88, 0.84), 0.5), 64, (1.02, -0.32, 0.0))
    green = mat("Sansevieria", (0.08, 0.22, 0.1), 0.45, sss=0.08, sss_radius=(0.01, 0.03, 0.01), sss_scale=0.01)
    nt, b = _nodes(green)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.65, 0.6, 0.2, 1)
    ramp.color_ramp.elements[1].position = 0.12
    ramp.color_ramp.elements[1].color = (0.08, 0.2, 0.09, 1)
    e = ramp.color_ramp.elements.new(0.88)
    e.color = (0.08, 0.2, 0.09, 1)
    e2 = ramp.color_ramp.elements.new(1.0)
    e2.color = (0.65, 0.6, 0.2, 1)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["UV"], sep.inputs[0])
    nt.links.new(sep.outputs["X"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    for k in range(9):
        hgt = rnd.uniform(0.55, 0.85)
        wid = rnd.uniform(0.05, 0.07)
        bm = bmesh.new()
        uv = bm.loops.layers.uv.new()
        rows = []
        bend = rnd.uniform(-0.12, 0.12)
        tw = rnd.uniform(-0.6, 0.6)
        for i in range(17):
            t = i / 16
            w = wid * (math.sin(math.pi * min(t * 1.25, 1.0)) ** 0.5) * (1 - 0.85 * t ** 3)
            a = tw * t
            cx = bend * t * t
            rows.append((bm.verts.new((cx - math.cos(a) * w / 2, -math.sin(a) * w / 2, hgt * t)),
                         bm.verts.new((cx + math.cos(a) * w / 2, math.sin(a) * w / 2, hgt * t)), t))
        for (l0, r0, t0), (l1, r1, t1) in pairwise(rows):
            f = bm.faces.new((l0, r0, r1, l1))
            for loop, (uu, vv) in zip(f.loops, ((0, t0), (1, t0), (1, t1), (0, t1))):
                loop[uv].uv = (uu, vv)
        lf = mesh_object(f"Blatt{k}", bm, green, (1.02 + rnd.uniform(-0.05, 0.05), -0.32 + rnd.uniform(-0.05, 0.05), 0.2),
                         (rnd.uniform(-0.15, 0.15), rnd.uniform(-0.15, 0.15), rnd.uniform(0, math.pi)))
        sol = lf.modifiers.new("Dicke", "SOLIDIFY")
        sol.thickness = 0.003
        _finish(lf)
    box("Erde", (0.2, 0.2, 0.01), mat("Erde", (0.08, 0.06, 0.045), 0.95), (1.02, -0.32, 0.24))
    # Fenster links (Schattenwurf) und Licht
    for nm, sz, loc in (("FensterO", (0.05, 2.0, 1.2), (-1.6, -1.2, 2.25)), ("FensterU", (0.05, 2.0, 0.8), (-1.6, -1.2, 0.3)),
                        ("FensterL", (0.05, 0.6, 1.0), (-1.6, -2.0, 1.2)), ("FensterR", (0.05, 0.4, 1.0), (-1.6, 0.0, 1.2)),
                        ("Sprosse", (0.05, 0.04, 1.0), (-1.6, -1.0, 1.2)), ("Sprosse2", (0.05, 1.0, 0.04), (-1.6, -1.0, 1.25))):
        box(nm, sz, mat("Fenster", (0.9, 0.9, 0.9), 0.6), loc)
    sun((0.82, 0.35, -0.42), 2.2, 1.2, (1.0, 0.9, 0.78))
    area((0.4, -2.2, 1.6), (0, 0, 1.0), 1.6, 45, (1.0, 0.96, 0.9))
    area((0, -0.9, 2.6), (0, -0.2, 0.9), 1.4, 18, (1.0, 0.97, 0.93))
    return {"target": (0.02, 0.0, 0.95), "S": 1.0, "cam": (-0.24, -1.08, 0.03), "lens": 40, "fstop": 0,
            "backdrop": False, "lights": False, "view": "agx", "world": (0.75, 0.82, 0.95), "world_strength": 0.25,
            "exposure": -0.2}


PRODUCTS = {
    "massageball": massageball,
    "eiskratzer": eiskratzer,
    "zugluftstopper": zugluftstopper,
    "tierhaar": tierhaar,
    "packwuerfel": packwuerfel,
    "baender": baender,
    "laptop": laptop,
    "frostschutz": frostschutz,
    "frostschutz_auto": frostschutz_auto,
    "fellhandschuh": fellhandschuh,
    "wandhaken": wandhaken,
    "rollbeutel": rollbeutel,
    "handystaender": handystaender,
    "wallpaper": wallpaper,
}
for _w in ("iceage", "medieval", "egypt", "jungle", "savanna", "arctic", "wildwest"):
    PRODUCTS[f"poster_{_w}"] = functools.partial(poster_room, world_key=_w)


# ----------------------------------------------------------------------------- Ablauf


def shoot(key: str, out: Path, size: int, samples: int, art: Path) -> Path:
    clear()
    spec = PRODUCTS[key](art)
    S = spec["S"]
    target = Vector(spec["target"])
    if spec.get("world", ()) is not None:
        world(spec.get("world", (0.93, 0.93, 0.95)), spec.get("world_strength", 0.35))
    if spec.get("backdrop", True):
        cyclorama(S, spec.get("bg", (0.93, 0.92, 0.90)), back=spec.get("back", 1.0))
    if spec.get("lights", True):
        studio_lights(target, S, spec.get("key", 1.0), spec.get("warm", False))
    cam = Vector(spec["cam"])
    camera(target + cam, target, spec.get("lens", 70), spec.get("fstop"), spec.get("shift", (0, 0)))
    setup_render(size, samples, spec.get("exposure", 0.0), spec.get("view", "neutral"))
    path = out / f"{key}.jpg"
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return path


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/shop/studio")
    ap.add_argument("--only", default="")
    ap.add_argument("--size", type=int, default=1200)
    ap.add_argument("--samples", type=int, default=128)
    ap.add_argument("--art", default="data/shop/kunst")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    keys = [k for k in a.only.split(",") if k] or list(PRODUCTS)
    for key in keys:
        random.seed(key)
        path = shoot(key, out, a.size, a.samples, Path(a.art))
        print(f"STUDIO {key} -> {path}", flush=True)


if __name__ == "__main__":
    main()
