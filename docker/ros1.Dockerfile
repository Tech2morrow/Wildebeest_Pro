FROM osrf/ros:noetic-desktop-full

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-catkin-tools python3-pip python3-rosdep python3-serial \
    ros-noetic-navigation ros-noetic-slam-gmapping ros-noetic-robot-localization \
    ros-noetic-ros-control ros-noetic-ros-controllers ros-noetic-gazebo-ros-control \
    ros-noetic-rosbridge-suite ros-noetic-teleop-twist-keyboard \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /wildebeest/ros1_ws
COPY ros1_ws/src ./src
COPY tests/fixtures /wildebeest/tests/fixtures
# gscam is an optional, hardware-specific Jetson camera integration and is not
# released through the Noetic rosdep index; the portable mock profile disables it.
RUN apt-get update && \
    source /opt/ros/noetic/setup.bash && \
    rosdep install --from-paths src --ignore-src --rosdistro noetic \
      --skip-keys gscam -r -y && \
    catkin_make && \
    catkin_make run_tests && \
    catkin_test_results build/test_results && \
    rm -rf /var/lib/apt/lists/*
COPY --chmod=755 docker/smoke_check.py /smoke_check.py
COPY --chmod=755 docker/ros_entrypoint.sh /ros_entrypoint.sh
ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["roslaunch", "wildebeest_bringup", "robot.launch", "use_sim:=true"]
