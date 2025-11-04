cmake_minimum_required(VERSION 3.18)

# Set the target platform for LLVM-MOS
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR mos)

# Project definition
project(c64_spellcheck C)

# Find LLVM-MOS SDK
find_package(llvm-mos-sdk REQUIRED)

# Set C standard
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Generate Bloom filter and config header first
add_custom_command(
    OUTPUT ${CMAKE_SOURCE_DIR}/build/generated/bloom_config.h
           ${CMAKE_SOURCE_DIR}/build/generated/bloom.dat
    COMMAND ${CMAKE_COMMAND} -E echo "Generating Bloom filter..."
    COMMAND python3 ${CMAKE_SOURCE_DIR}/src/python/build_bloom.py
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    COMMENT "Building Bloom filter data"
)

# Add executable
add_executable(spellcheck
    src/spellcheck.c
    ${CMAKE_SOURCE_DIR}/build/generated/bloom_config.h
)

# Include generated header directory
target_include_directories(spellcheck PRIVATE
    ${CMAKE_SOURCE_DIR}/build/generated
)

# Target C64
target_compile_options(spellcheck PRIVATE
    -Os  # Optimize for size
)

# Set output to artifacts directory
set_target_properties(spellcheck PROPERTIES
    OUTPUT_NAME "spellcheck"
    SUFFIX ".prg"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/build/artifacts"
)

# Custom target to create disk image after build
add_custom_command(TARGET spellcheck POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E echo "Creating disk image..."
    COMMAND python3 ${CMAKE_SOURCE_DIR}/src/python/build_bloom.py
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    COMMENT "Creating C64 disk image"
)
