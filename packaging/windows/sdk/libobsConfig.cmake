# libobsConfig.cmake -- find_package(libobs) for obsmage's Windows cross build (packaging/windows/omg-win).
# Not OBS's own config: it names OBS Studio's headers at the pinned commit and the import library dlltool made
# from obs.def. omg-win passes OBS_LIBOBS_INCLUDE (header folders) and OBS_SDK_LIB (import libraries).
if(NOT TARGET OBS::libobs)
  add_library(OBS::libobs UNKNOWN IMPORTED)
  set_target_properties(OBS::libobs PROPERTIES
    IMPORTED_LOCATION "${OBS_SDK_LIB}/libobs.dll.a"
    INTERFACE_INCLUDE_DIRECTORIES "${OBS_LIBOBS_INCLUDE}")
endif()
set(libobs_FOUND TRUE)

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin, claude-opus-5-5)
