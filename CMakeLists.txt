cmake_minimum_required(VERSION 3.21)
project(Drakengard_Recomp LANGUAGES C CXX)

# Drakengard (EU, SLES-52322) static recompilation on top of PS2Recomp, built with GCC (MSYS2 UCRT64 on Windows):
# scripts/build_runner_gcc.sh. The recompiled code and the override module are installed into the runner's
# source folder by scripts/sync_runner.py, so PS2Recomp's ps2EntryRunner target picks them up; this project adds
# the VU microcode compiled ahead of time.

# Only the runtime is needed here; the recompiler/analyzer are built by scripts/build_tools.bat.
set(PS2X_BUILD_RECOMP OFF CACHE BOOL "" FORCE)
set(PS2X_BUILD_ANALYZER OFF CACHE BOOL "" FORCE)
set(PS2X_BUILD_TEST OFF CACHE BOOL "" FORCE)
set(PS2X_BUILD_STUDIO OFF CACHE BOOL "" FORCE)

add_subdirectory(PS2Recomp)

# VU0/VU1 microcode compiled ahead of time (ps2_vu_aot game/SLES_523.22 recomp/vu1_aot): an object library outside
# the unity batches. -O3 unrolls the operand loops over each pair's constexpr decode and debug info only slows the
# build. Each file takes GCC a few GB, so at most 4 compile at once. MSVC takes minutes per file (its optimizer
# chokes on the inlined interpreter bodies), hence the switch to GCC.
option(DRAKENGARD_VU_AOT "Link the VU microcode compiled ahead of time from recomp/vu1_aot" ON)
file(GLOB DRAKENGARD_VU_AOT_SOURCES CONFIGURE_DEPENDS "${CMAKE_SOURCE_DIR}/recomp/vu1_aot/*.cpp")
if(DRAKENGARD_VU_AOT AND DRAKENGARD_VU_AOT_SOURCES)
    set_property(GLOBAL APPEND PROPERTY JOB_POOLS drakengard_vu_aot=4)
    add_library(drakengard_vu_aot OBJECT ${DRAKENGARD_VU_AOT_SOURCES})
    target_link_libraries(drakengard_vu_aot PRIVATE ps2_runtime)
    set_target_properties(drakengard_vu_aot PROPERTIES UNITY_BUILD OFF JOB_POOL_COMPILE drakengard_vu_aot)
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(drakengard_vu_aot PRIVATE -O3 -g0)
    endif()
    target_sources(ps2EntryRunner PRIVATE $<TARGET_OBJECTS:drakengard_vu_aot>)
    list(LENGTH DRAKENGARD_VU_AOT_SOURCES _aot_count)
    message(STATUS "Drakengard_Recomp: ${_aot_count} VU microcode files compiled ahead of time")
endif()
