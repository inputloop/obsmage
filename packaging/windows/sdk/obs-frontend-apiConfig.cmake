# obs-frontend-apiConfig.cmake -- find_package(obs-frontend-api) for obsmage's Windows cross build (see
# libobsConfig.cmake beside it). omg-win passes OBS_FRONTEND_INCLUDE and OBS_SDK_LIB.
if(NOT TARGET OBS::obs-frontend-api)
  add_library(OBS::obs-frontend-api UNKNOWN IMPORTED)
  set_target_properties(OBS::obs-frontend-api PROPERTIES
    IMPORTED_LOCATION "${OBS_SDK_LIB}/libobs-frontend-api.dll.a"
    INTERFACE_INCLUDE_DIRECTORIES "${OBS_FRONTEND_INCLUDE}")
endif()
set(obs-frontend-api_FOUND TRUE)

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin, claude-opus-5-5)
