# Third-party and CAD asset notice

The root MIT license covers original Wildebeest Pro software and documentation contributed under that license. It does **not** automatically relicense third-party material embedded in the mechanical-design corpus.

## CAD/reference assets

`3D_Mechanical_Design/P&G Wildebeest_Pro/` contains a complete project assembly plus reference models, appearances, textures, and scene files whose filenames identify or resemble commercial components. Examples include NVIDIA Jetson Nano, Arduino Uno, Noctua NF-A4x20, IMX219, u-blox/GNSS, MPU6050, L298N/LM2596 modules, connectors, battery cells, and SolidWorks appearance assets. `assets/cad-render.png` is a rendered derivative of that assembly and carries the same provenance caveat.

No reliable per-asset license or provenance metadata was found alongside many of these files during the 2026-09-10 repository audit. Their inclusion preserves the existing design and is not a statement that every asset is owned by the project, redistributable under MIT, approved by a vendor, or suitable for commercial manufacture.

Before redistributing, selling, or using the CAD corpus commercially, users must:

1. identify the source and applicable terms for each reference model, texture, and appearance;
2. replace or remove any asset for which they cannot establish appropriate rights;
3. respect applicable trademark, design, export, and product-documentation requirements; and
4. obtain independent legal advice where the intended use requires it.

Product names and marks remain the property of their respective owners. References describe compatibility or design intent and do not imply endorsement.

## Runtime dependencies

ROS, Gazebo, Nav2, robot_localization, rosbridge, PlatformIO, Arduino libraries, MkDocs Material, Blender, Docker images, and other dependencies are obtained separately and remain under their own licenses. Review the packages installed for the selected runtime and distribute their notices as required.

If you can document the original source and license of an asset, please open a contribution with that evidence so this notice and the CAD manifest can be made more precise.
