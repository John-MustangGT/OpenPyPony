cmake_minimum_required(VERSION 3.13)
include(pico_sdk_import.cmake)

project(openpony_pico)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

# ----------------------
# Sources
# ----------------------
add_executable(openpony
    src/main.c
    src/producer.c
    src/consumer_sd.c
    src/ring_buffer.c
    src/drivers/lis3dh.c
    src/drivers/gps.c
    src/binary_logger.c
    src/sd_mount.c
)

target_include_directories(openpony PRIVATE include)

# ----------------------
# Core SDK libs
# ----------------------
target_link_libraries(openpony PRIVATE
    pico_stdlib
    hardware_i2c
    hardware_uart
    hardware_spi
    pico_multicore
    pico_time
)

# ----------------------
# Optional: pico-extras / FatFS / SD card helpers
# ----------------------
# pico-extras exports different target names depending on how it's added to the build.
# The following conditional blocks attempt to pick the most common exported targets.
# If your pico-extras exposes different target names, update these lines accordingly.
#
# Typical targets you may see in pico-extras:
#  - pico_extras_ff        (FatFS helpers)
#  - pico_sd_card          (sd card block device / helpers)
#  - pico_sd                (alternative name)
#  - pico_extras           (umbrella - may include ff)
#

if(TARGET pico_extras_ff)
    message(STATUS "Linking pico_extras_ff")
    target_link_libraries(openpony PRIVATE pico_extras_ff)
elseif(TARGET pico_extras)
    message(STATUS "Linking pico_extras (may include FatFS)")
    target_link_libraries(openpony PRIVATE pico_extras)
endif()

if(TARGET pico_sd_card)
    message(STATUS "Linking pico_sd_card")
    target_link_libraries(openpony PRIVATE pico_sd_card)
elseif(TARGET pico_sd)
    message(STATUS "Linking pico_sd")
    target_link_libraries(openpony PRIVATE pico_sd)
endif()

# If your project adds pico-extras as a subdirectory, ensure you add it before this CMakeLists
# or link to the correct exported targets from pico-extras. Example:
#   add_subdirectory(path/to/pico_extras)
# Then the targets above will be available.

# ----------------------
# Finalize
# ----------------------
pico_add_extra_outputs(openpony)