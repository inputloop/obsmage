# obsmage-core -- the always-present obsmage plugin: Tools-menu entries for calibration and the
# screen-map composer. Builds against an installed libobs + obs-frontend-api (upstream OBS or ours).
# STATUS: skeleton; builds against Ubuntu 26.04 libobs-dev and loads in OBS 32.1.0 (gw33, 2026-11-01).
# For Windows it is cross-built with MinGW-w64 by packaging/windows/omg-win, which supplies the two packages.
# The version below must equal debian/changelog's (omg-win refuses to build otherwise); the code reads it from here.
cmake_minimum_required(VERSION 3.22)
project(obsmage-core VERSION 0.0.1 LANGUAGES C)

find_package(libobs REQUIRED)
find_package(obs-frontend-api REQUIRED)

add_library(obsmage-core MODULE src/plugin-main.c)
target_compile_definitions(obsmage-core PRIVATE OBSMAGE_VERSION="${PROJECT_VERSION}")
target_link_libraries(obsmage-core PRIVATE OBS::libobs OBS::obs-frontend-api)
set_target_properties(obsmage-core PROPERTIES PREFIX "")

install(TARGETS obsmage-core LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}/obs-plugins")
install(DIRECTORY data/ DESTINATION "share/obs/obs-plugins/obsmage-core")

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin; claude-opus-5-5)
