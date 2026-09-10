# Bill of materials

[`Wildebeest_Pro_BOM.xlsx`](Wildebeest_Pro_BOM.xlsx) is the working hardware and
commissioning record. Filter by subsystem or status, enter supplier costs in the
yellow cells, and move a line to **Verified** only after inspecting or measuring
the actual part.

The drive rows reflect the audited four-wheel skid-steer assembly: four geared
motors and four wheels, with front/rear motors paired by side. The L298N remains
a blocker until each channel is proven against the combined side-pair current.

The workbook intentionally opens with a **BLOCKED** release gate. The original
concept did not identify several safety-critical selections: cell specification,
2S BMS, fuse, physical E-stop contacts, power distribution, motor stall current,
proper wheel encoders and the custom LiDAR interface. Resolve those rows before
powered floor testing.
