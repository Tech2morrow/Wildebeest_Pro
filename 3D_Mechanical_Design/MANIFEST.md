# CAD and mesh manifest

Audit date: 2026-09-10

This is a curated manifest for the large mechanical corpus in
`P&G Wildebeest_Pro/`. It identifies authoritative files and integration risks
without duplicating hundreds of generated component paths.

## Authoritative artifacts

| Purpose | File | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| Top-level native assembly | `Wildebeest_Pro_P&G.SLDASM` | 29,494,243 | `162D7D639AF203026D1699CD1CCE04777310D2187BA0D0FB7B2A0BE41C8F1110` |
| Full neutral assembly | `Wildebeest_Pro_P&G.STEP` | 177,374,833 | `423240EAEA069CD2CBF77FAEBC2609E1ACF4ED85AA4D9643296FB8CCB0925821` |
| Mobile-base subassembly | `Wildebeest_Nano.SLDASM` | 27,725,590 | `90F0D0D6D6009D073ED9B8FF8CA01DFBC3788B2C229E7CEF037FDC3F30640184` |
| LiDAR mounting plate | `LiDAR Plate.SLDPRT` | 52,600 | `244359235453B6E345CC5B0F83FF48933B2BB676D49AAFD1D3411C4AF1831840` |
| LiDAR plate mesh | `Wildebeest_Pro_P&G - LiDAR Plate-1.STL` | 1,484 | `20439837C4C6CBF34C9FCD64C5D5F5638B4BA27D4E14962C89A501D33BE7E319` |
| Radar-labelled sensor part | `Radar_mb_1r2t_v1.SLDPRT` | 406,771 | `D6C11294351D1CBC77754A92F3E1E73B76188B0AE3EABCEBA7CD79E90DC1C04C` |
| Radar-labelled neutral part | `Radar_mb_1r2t_v1.step` | 244,302 | `AA2ADC3C804F8225A5D29B2D92C611D475255397680E2959B6AC9AF039D2652E` |
| Radar-labelled placed mesh | `Wildebeest_Pro_P&G - Radar_mb_1r2t_v1-1.STL` | 811,684 | `70F614AFFF7E5FB44CBEB4F7AFCC7520ABD0AFA1F21CA2DE5679CBE83A33A4E3` |

The STEP header reports `SolidWorks 2025`, schema `CONFIG_CONTROL_DESIGN`
(AP203), and `SI_UNIT (.MILLI., .METRE.)` for length.

## Corpus summary

| Extension | Files | Bytes |
| --- | ---: | ---: |
| `.STL` | 595 | 141,496,180 |
| `.SLDPRT` | 59 | 54,908,882 |
| `.SLDASM` | 23 | 131,568,114 |
| `.STEP` | 3 | 177,644,837 |
| `.stp` | 1 | 1,731,524 |

The full directory contains 761 files and 539,451,840 bytes (514.46 MiB),
including SolidWorks appearances and scene assets. Every STL is binary; together
they contain 2,828,924 triangles. The STL files are all byte-distinct because
the assembly export baked component placement into vertex coordinates.

## Geometry observations

The union of all placed STL vertices is:

| Axis | Minimum (mm) | Maximum (mm) | Span (mm) |
| --- | ---: | ---: | ---: |
| X | 0.280 | 171.578 | 171.298 |
| Y | 88.255 | 243.898 | 155.642 |
| Z | 92.691 | 368.696 | 276.005 |

The four wheel meshes each measure approximately
`25.07 × 67.25 × 67.24 mm`. Their bounding-box centres imply a nominal wheel
radius near `0.03362 m`, left/right centre spacing near `0.12184 m`, and
front/rear centre spacing near `0.11715 m` under the apparent CAD-axis
interpretation. These are **audit clues only**: verify axis interpretation,
tire compression, and physical measurements before changing kinematic
parameters.

The LiDAR plate mesh spans about `100 × 1.5 × 132 mm`. The STEP product table
names the plate and `Radar_mb_1r2t_v1`, but it does not name an actual LiDAR
device. Consequently, this repository cannot yet assert a LiDAR make/model,
scan plane, connector clearance, field of view, or optical-frame transform from
CAD alone.

## Lightweight ROS mesh release policy

Do not copy the raw STEP file or all 595 STLs into both ROS workspaces. Produce
one versioned mesh set and share the same source artifacts between ROS 1 and
ROS 2 packaging:

1. Open the full STEP/native assembly and suppress cables, PCB micro-components,
   threads, fasteners, internal electronics, and appearance-only details.
2. Split only at moving or independently framed links: chassis, four wheels,
   and sensor/mast elements that need their own TF.
3. Normalize each link to its joint frame and REP-103 orientation.
4. Export a decimated `.dae` visual mesh in metres; target a complete-robot
   visual budget well below 100,000 triangles.
5. Model collision with boxes/cylinders or a small set of convex hulls. Never
   reuse detailed visual meshes for physics collision.
6. Store released meshes once in the description package and track them with
   Git LFS. ROS 1 and ROS 2 should consume equivalent generated artifacts,
   rather than keeping divergent manual copies.
7. Record source CAD revision, export settings, scale, axes, triangle count,
   and SHA-256 in this manifest for every released mesh.

Until that pipeline is reviewed, the parametric primitive descriptions are the
safe, portable default for RViz and simulation.
