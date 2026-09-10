# wildebeest_navigation

This package provides a conservative Nav2 configuration, SLAM Toolbox tuning,
an RViz workspace, and a deliberately obvious placeholder map.

Start `wildebeest_bringup` first, verify `/scan`,
`/odometry/filtered`, and the full TF tree, then map:

```bash
ros2 launch wildebeest_navigation navigation.launch.py slam:=true
ros2 run nav2_map_server map_saver_cli -f ~/maps/wildebeest_site
```

Navigate using the saved map:

```bash
ros2 launch wildebeest_navigation navigation.launch.py \
  slam:=false map:=$HOME/maps/wildebeest_site.yaml
```

Nav2 output is remapped to `/cmd_vel/navigation`; the bringup mux turns that
into the stable `/cmd_vel` consumed by the base. The velocity smoother feeds
Nav2's collision monitor before that mux output, and the local costmap uses
both the 2D lidar and `/range/front`. Route and docking servers have safe
baseline configuration but require site-specific graphs, dock poses, and
commissioning before use. Software collision layers improve behavior but are
not safety-rated.

Before autonomous use, replace the example map and measure/tune the footprint,
inflation radius, lidar range, velocity/acceleration limits, controller,
planner, and recovery behaviors.  Test with motor power disabled first, then
on blocks, then in a bounded low-speed area with a physical estop operator.
The initial footprint follows the CAD cover envelope (`0.257 x 0.150 m`) plus
costmap padding; include every real protrusion when commissioning it.
