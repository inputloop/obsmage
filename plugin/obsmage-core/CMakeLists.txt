# obsmage-core -- the always-present obsmage plugin: Tools-menu entries for calibration and the
# screen-map composer. Builds against an installed libobs + obs-frontend-api (upstream OBS or ours).
# STATUS: skeleton; builds against Ubuntu 26.04 libobs-dev (checked on gw33, 2026-11-01).
cmake_minimum_required(VERSION 3.22)
project(obsmage-core VERSION 0.0.1 LANGUAGES C)

find_package(libobs REQUIRED)
find_package(obs-frontend-api REQUIRED)

add_library(obsmage-core MODULE src/plugin-main.c)
target_link_libraries(obsmage-core PRIVATE OBS::libobs OBS::obs-frontend-api)
set_target_properties(obsmage-core PROPERTIES PREFIX "")

install(TARGETS obsmage-core LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}/obs-plugins")
install(DIRECTORY data/ DESTINATION "share/obs/obs-plugins/obsmage-core")

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin; claude-opus-5-5)
