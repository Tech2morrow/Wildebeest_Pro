.DEFAULT_GOAL := help
.PHONY: help test doctor dashboard ros2 ros1 firmware docs

PYTHON ?= python3

help:
	@echo "Wildebeest Pro targets"
	@echo "  make test       Dependency-free host and dashboard tests"
	@echo "  make doctor     Repository and commissioning preflight"
	@echo "  make dashboard  Operator UI at http://127.0.0.1:8088"
	@echo "  make ros2       Build the ROS 2 workspace"
	@echo "  make ros1       Build the ROS 1 workspace"
	@echo "  make firmware   Build Arduino firmware with PlatformIO"
	@echo "  make docs       Build the MkDocs site"

test:
	$(PYTHON) -m unittest discover -s tools/tests -v
	node --test dashboard/test/*.test.mjs

doctor:
	$(PYTHON) tools/robot_doctor.py

dashboard:
	node dashboard/dev-server.mjs

ros2:
	./scripts/build.sh ros2

ros1:
	./scripts/build.sh ros1

firmware:
	./scripts/build.sh firmware

docs:
	./scripts/build.sh docs
