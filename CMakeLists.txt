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

# Add executable
add_executable(spellcheck
    src/spellcheck.c
)

# Target C64
target_compile_options(spellcheck PRIVATE
    -Os  # Optimize for size
)

# Set output name
set_target_properties(spellcheck PROPERTIES
    OUTPUT_NAME "spellcheck"
    SUFFIX ".prg"
)

# Custom target to run Python script after build
add_custom_command(TARGET spellcheck POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E echo "Running Bloom filter build script..."
    COMMAND python3 ${CMAKE_SOURCE_DIR}/tools/build_bloom.py
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    COMMENT "Building Bloom filter and creating disk image"
)

# Install target (copies to build directory)
install(TARGETS spellcheck
    DESTINATION ${CMAKE_BINARY_DIR}
)
