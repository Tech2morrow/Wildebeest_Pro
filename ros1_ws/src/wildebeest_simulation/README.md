# Wildebeest Gazebo Classic simulation

Run `roslaunch wildebeest_simulation demo.launch` after building and sourcing the workspace. The launch starts Gazebo, `gazebo_ros_control`, encoder/IMU/LiDAR/camera/range sensor plugins, the same local EKF and navigation configuration used by hardware, a command multiplexer, and RViz. Send a 2D Nav Goal in RViz.

The model has four independently named wheel links, joints, and transmissions. Noetic's established `diff_drive_controller` multi-wheel mode commands both front/rear joints on each side and averages their feedback, preserving the hardware protocol's single left/right side velocities. Gazebo uses reduced lateral wheel friction to permit skid-steer scrub. CAD geometry (0.033622 m radius, 0.025065 m width, 0.121843 m track, 0.117150 m wheelbase, 0.257 x 0.150 x 0.031 m shell) is nominal; tyre friction, effective track, mass, inertia, and controller gains require physical calibration.

Gazebo Classic and ROS Noetic are both legacy software. The simulation is an integration and learning environment, not evidence that the physical robot is safe or calibrated. Optional GPS simulation requires `hector_gazebo_plugins` and `simulate_gps:=true` on `gazebo.launch`.
