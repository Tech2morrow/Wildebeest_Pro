# Wildebeest navigation (ROS 1)

`localization.launch` always starts the local encoder/IMU EKF (`odom -> base_link`). Enable its GPS group only for outdoor GNSS localization. `navigation.launch` starts map server, AMCL, and `move_base`; AMCL owns `map -> odom` in that mode. Do not enable the global GPS EKF, AMCL, and GMapping at the same time because they compete for the same transform.

The supplied `demo.pgm` is only a launch smoke-test map. Create a site map with `mapping.launch`, inspect it, and pass the resulting YAML through the `map:=` launch argument. The costmap footprint is based on the nominal 0.257 x 0.150 m CAD cover with a small margin. Planner limits, protrusions, effective skid-steer track, footprint, and localization noise must be measured on the assembled robot.
