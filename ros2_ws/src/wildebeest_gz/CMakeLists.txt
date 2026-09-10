cmake_minimum_required(VERSION 3.16)
project(wildebeest_gz)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(DIRECTORY config launch worlds
  DESTINATION share/${PROJECT_NAME}
)
install(FILES README.md
  DESTINATION share/${PROJECT_NAME}
)
install(PROGRAMS
  scripts/range_contract_adapter
  scripts/safety_twist_gate
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_range_contract test/test_range_contract.py)
  ament_add_pytest_test(test_safety_gate test/test_safety_gate.py)
endif()

ament_package()
