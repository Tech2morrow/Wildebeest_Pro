"""Render the placed SolidWorks STL export set with Blender.

Run from the repository root:

    blender --background --python tools/render_cad.py -- \
      --output assets/cad-render.png

The assembly export stores millimetre coordinates in 595 independent binary
STLs.  This script applies the audited CAD-to-REP-103 axis mapping for a
presentation image only.  It does not manufacture link-local URDF meshes and
must not be used as a source of calibrated transforms.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


CAD_CENTER_X_MM = 94.0376
CAD_GROUND_Y_MM = 88.2548
CAD_CENTER_Z_MM = 221.1913
MM_TO_M = 0.001


def arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="assets/cad-render.png")
    parser.add_argument("--samples", type=int, default=64)
    return parser.parse_args(argv)


def material(name: str, rgba: tuple[float, float, float, float], metallic=0.0, roughness=0.4):
    result = bpy.data.materials.new(name)
    result.diffuse_color = rgba
    result.metallic = metallic
    result.roughness = roughness
    return result


def choose_material(filename: str, palette: dict[str, object]):
    name = filename.lower()
    if "wheel-" in name:
        return palette["rubber"]
    if any(token in name for token in ("bottom_cover", "top_cover", "support_")):
        return palette["body"]
    if any(token in name for token in ("lidar", "radar")):
        return palette["sensor"]
    if any(token in name for token in ("camera", "imx219", "ultrasonic")):
        return palette["optic"]
    if any(token in name for token in ("jetson", "arduino", "l298n", "gps", "mpu 6050", "pcb")):
        return palette["electronics"]
    if any(token in name for token in ("battery", "18650")):
        return palette["battery"]
    if any(token in name for token in ("cable", "harness", "jumber", "ribbon", "wire")):
        return palette["cable"]
    return palette["metal"]


def point_at(obj, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def main() -> None:
    args = arguments()
    root = Path(__file__).resolve().parents[1]
    source = root / "3D_Mechanical_Design" / "P&G Wildebeest_Pro"
    files = sorted(source.glob("Wildebeest_Pro_P&G -*.STL"))
    if len(files) != 595:
        raise RuntimeError(f"expected 595 placed STL exports, found {len(files)}")

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    palette = {
        "body": material("Wildebeest teal", (0.015, 0.34, 0.38, 1.0), metallic=0.45, roughness=0.24),
        "rubber": material("Tire rubber", (0.012, 0.018, 0.024, 1.0), roughness=0.72),
        "sensor": material("LiDAR amber", (1.0, 0.27, 0.035, 1.0), metallic=0.12, roughness=0.25),
        "optic": material("Optics", (0.018, 0.055, 0.075, 1.0), metallic=0.28, roughness=0.18),
        "electronics": material("Electronics", (0.05, 0.48, 0.34, 1.0), metallic=0.08, roughness=0.42),
        "battery": material("Battery", (0.28, 0.34, 0.40, 1.0), metallic=0.35, roughness=0.3),
        "cable": material("Cables", (0.025, 0.032, 0.045, 1.0), roughness=0.65),
        "metal": material("Hardware", (0.36, 0.43, 0.49, 1.0), metallic=0.72, roughness=0.24),
    }

    # ROS x=CAD Z, ROS y=CAD X, ROS z=CAD Y.  Translate wheel midpoint to
    # x/y zero and the audited lowest mesh point to the presentation ground.
    cad_to_world = Matrix(
        (
            (0.0, 0.0, MM_TO_M, -CAD_CENTER_Z_MM * MM_TO_M),
            (MM_TO_M, 0.0, 0.0, -CAD_CENTER_X_MM * MM_TO_M),
            (0.0, MM_TO_M, 0.0, -CAD_GROUND_Y_MM * MM_TO_M),
            (0.0, 0.0, 0.0, 1.0),
        )
    )

    for index, path in enumerate(files, start=1):
        bpy.ops.object.select_all(action="DESELECT")
        bpy.ops.wm.stl_import(filepath=str(path))
        imported = list(bpy.context.selected_objects)
        if not imported:
            raise RuntimeError(f"Blender did not import {path.name}")
        for obj in imported:
            obj.name = f"cad_{index:03d}"
            obj.matrix_world = cad_to_world
            obj.data.materials.clear()
            obj.data.materials.append(choose_material(path.name, palette))
        if index % 50 == 0:
            print(f"Imported {index}/{len(files)} placed components")

    # Ground plinth.
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=0.31, depth=0.018, location=(0, 0, -0.012))
    plinth = bpy.context.object
    plinth.data.materials.append(material("Plinth", (0.018, 0.027, 0.042, 1.0), metallic=0.5, roughness=0.28))
    bevel = plinth.modifiers.new("Soft rim", "BEVEL")
    bevel.width = 0.009
    bevel.segments = 4

    # Camera and lighting chosen to show the front sensor cluster and all four
    # wheel positions while keeping the audited proportions legible.
    bpy.ops.object.camera_add(location=(0.62, -0.55, 0.42))
    camera = bpy.context.object
    camera.data.lens = 58
    point_at(camera, Vector((0.010, 0.0, 0.085)))
    bpy.context.scene.camera = camera

    def area(location, energy, size, color):
        bpy.ops.object.light_add(type="AREA", location=location)
        lamp = bpy.context.object
        lamp.data.energy = energy
        lamp.data.shape = "DISK"
        lamp.data.size = size
        lamp.data.color = color
        point_at(lamp, Vector((0.0, 0.0, 0.09)))

    area((0.22, -0.30, 0.48), 780, 0.28, (0.72, 0.92, 1.0))
    area((-0.28, 0.24, 0.34), 560, 0.24, (1.0, 0.45, 0.19))
    area((-0.08, -0.08, 0.50), 430, 0.18, (0.82, 1.0, 0.94))

    scene = bpy.context.scene
    # Workbench renders reliably in headless CI / integrated-GPU environments
    # where Eevee compute shaders may be unavailable.
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.filepath = str((root / args.output).resolve())
    scene.render.image_settings.color_mode = "RGBA"
    scene.world.color = (0.006, 0.010, 0.020)
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "paint.sl"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.background_type = "VIEWPORT"
    scene.display.shading.background_color = (0.006, 0.010, 0.020)
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    scene.display.shading.curvature_ridge_factor = 1.6
    scene.display.shading.curvature_valley_factor = 1.2
    scene.display.shading.show_specular_highlight = True
    try:
        scene.render.image_settings.color_depth = "8"
        scene.view_settings.look = "AgX - Medium High Contrast"
    except (AttributeError, TypeError):
        pass

    scene.render.resolution_percentage = 100
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {len(files)} components to {scene.render.filepath}")


if __name__ == "__main__":
    main()
