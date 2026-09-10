# Datasheets and controlled references

Do not commit vendor PDFs without checking redistribution terms. Store local
copies outside the repository or add only files whose licenses permit it. Record
the exact manufacturer, part number, hardware revision, URL, document revision
and retrieval date in the BOM.

The minimum controlled set is:

- Jetson module/carrier and power-mode documentation
- Arduino Uno R3 electrical limits and pin map
- selected motor and quadrature encoder datasheets
- selected motor-driver, regulator, cells, BMS and fuse datasheets
- exact LiDAR protocol/timing documentation
- MPU-6050, GNSS, IMX219 and HC-SR04 module documentation

Module/carrier boards often differ from the underlying chip datasheet. Verify
the actual breakout board's regulator, pull-ups and logic levels as well.
