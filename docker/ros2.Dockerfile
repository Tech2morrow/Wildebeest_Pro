FROM osrf/ros:jazzy-desktop-full

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-colcon-common-extensions python3-pip python3-rosdep python3-serial \
    ros-jazzy-navigation2 ros-jazzy-nav2-bringup ros-jazzy-slam-toolbox \
    ros-jazzy-robot-localization ros-jazzy-ros2-control ros-jazzy-ros2-controllers \
    ros-jazzy-ros-gz ros-jazzy-rosbridge-suite ros-jazzy-teleop-twist-keyboard \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /wildebeest/ros2_ws
COPY ros2_ws/src ./src
COPY tests/fixtures /wildebeest/tests/fixtures
RUN apt-get update && \
    source /opt/ros/jazzy/setup.bash && \
    rosdep install --from-paths src --ignore-src --rosdistro jazzy -r -y && \
    colcon build --symlink-install && \
    source install/setup.bash && \
    colcon test --event-handlers console_direct+ && \
    colcon test-result --verbose && \
    rm -rf /var/lib/apt/lists/*
COPY --chmod=755 docker/smoke_check.py /smoke_check.py
COPY --chmod=755 docker/ros_entrypoint.sh /ros_entrypoint.sh
ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["ros2", "launch", "wildebeest_bringup", "robot.launch.py", "use_sim:=true"]
