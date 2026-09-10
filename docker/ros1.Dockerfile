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
RUN source /opt/ros/noetic/setup.bash && \
    rosdep install --from-paths src --ignore-src --rosdistro noetic -r -y && \
    catkin_make && \
    catkin_make run_tests && \
    catkin_test_results build/test_results
COPY --chmod=755 docker/ros_entrypoint.sh /ros_entrypoint.sh
ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["roslaunch", "wildebeest_bringup", "robot.launch", "use_sim:=true"]
