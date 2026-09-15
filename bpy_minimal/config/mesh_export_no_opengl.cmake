# Einzelfaktor-Experiment: Baseline ohne OpenGL-Backend.
include("${CMAKE_CURRENT_LIST_DIR}/mesh_export.cmake")

set(WITH_OPENGL_BACKEND OFF CACHE BOOL "" FORCE)
