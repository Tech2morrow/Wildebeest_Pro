# Wildebeest Pro mechanical design

This directory preserves the native SolidWorks design, a neutral STEP export,
and the component-level STL export set for the complete robot assembly.

Some component models, textures, and appearances have unconfirmed third-party
provenance. Read the repository [third-party notice](../THIRD_PARTY_NOTICES.md)
before redistributing or using the CAD corpus commercially.

## Start here

The authoritative top-level assembly is
[`Wildebeest_Pro_P&G.SLDASM`](<P&G Wildebeest_Pro/Wildebeest_Pro_P&G.SLDASM>).
The `.asm` filename mentioned in early project notes does not exist; `.SLDASM`
is the native SolidWorks assembly extension.

Users without SolidWorks can open the matching AP203 exchange model,
[`Wildebeest_Pro_P&G.STEP`](<P&G Wildebeest_Pro/Wildebeest_Pro_P&G.STEP>),
in a STEP-capable CAD program. There is **no single master assembly STL** in
this revision. The 595 `.STL` files are per-component exports whose filenames
begin with `Wildebeest_Pro_P&G -`.

Large CAD and mesh files are stored with Git LFS. After cloning, retrieve them
before opening the model:

```bash
git lfs install
git lfs pull
```

See [MANIFEST.md](MANIFEST.md) for checksums, measured mesh bounds, the sensor
evidence in the assembly, and the ROS export policy.

## Units and coordinate handling

The STEP file explicitly declares millimetres. STL does not carry unit
metadata, but the component coordinates match the millimetre-scale STEP model.
Unmodified STL files therefore require a `0.001` scale in URDF/Xacro.

Do not treat the current CAD origin or axes as a ROS frame. Before publishing a
production mesh:

1. Reorient it to REP-103 (`x` forward, `y` left, `z` up).
2. Put the base origin on the ground-plane projection of the chassis centre.
3. Export in metres, or explicitly apply `scale="0.001 0.001 0.001"`.
4. Use a decimated mesh for visuals and primitives or convex hulls for
   collision. Never use the 2.8-million-triangle component set as collision
   geometry.
5. Keep one normalized mesh per rigid ROS link. The assembly-exported STLs have
   transforms baked into their vertex coordinates and are not link-local.

The checked-in ROS descriptions intentionally use lightweight primitives until
a normalized, reviewed visual mesh is released. That keeps cloning, simulation,
collision checking, and CI practical.

## LiDAR and ranging-model status

The assembly contains `LiDAR Plate.SLDPRT` and its component STL. It also
contains a sensor model named `Radar_mb_1r2t_v1` in SolidWorks, STEP, and STL
formats. No RPLIDAR, YDLIDAR, LDS, or other explicitly named LiDAR sensor body
was found in the native/exchange corpus. Confirm the physical sensor model and
measure its optical origin before setting `laser_frame` or driver parameters.

## Engineering release checklist

Before manufacturing or hardware commissioning:

1. Resolve suppressed or missing references in the original SolidWorks version.
2. Assign real materials, mass, inertia, and centre-of-mass properties.
3. Check interference, fastener engagement, cable bend radius, ventilation,
   wheel clearance, and service access.
4. Create controlled drawings with tolerances and revision identifiers.
5. Measure the assembled wheel radius, left/right wheel-centre separation, and
   every sensor transform. CAD-derived values in the manifest are useful
   cross-checks, not substitutes for measurement.
