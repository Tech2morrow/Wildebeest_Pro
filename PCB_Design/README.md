# Electronics design status

The concept repository did not contain an editable schematic or PCB layout. The
current reference implementation therefore uses a documented, fused wiring
harness and off-the-shelf modules; it does **not** pretend that an unreviewed PCB
exists.

Before creating a carrier PCB, freeze the selected motor driver, regulator,
LiDAR interface, connectors and peak-current budget. A releasable design must
include source schematics, ERC/DRC reports, fabrication outputs, assembly BOM,
pick-and-place data, connector pinout, mounting drawing, revision marking,
power-on test plan and a license. See [`docs/hardware/wiring.md`](../docs/hardware/wiring.md)
for the current interconnect contract.
