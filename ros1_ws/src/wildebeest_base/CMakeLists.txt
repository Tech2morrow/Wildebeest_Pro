cmake_minimum_required(VERSION 3.0.2)
project(wildebeest_base)

find_package(catkin REQUIRED COMPONENTS
  diagnostic_msgs
  geometry_msgs
  nav_msgs
  rospy
  sensor_msgs
  std_msgs
  std_srvs
  tf2_ros
)

catkin_python_setup()

catkin_package(
  CATKIN_DEPENDS diagnostic_msgs geometry_msgs nav_msgs rospy sensor_msgs std_msgs std_srvs tf2_ros
)

catkin_install_python(PROGRAMS
  scripts/serial_bridge_node.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY config launch docs firmware
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)

if(CATKIN_ENABLE_TESTING)
  catkin_add_nosetests(test)
endif()
