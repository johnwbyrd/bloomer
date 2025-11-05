cmake_minimum_required(VERSION 3.18)

# Find mos-c64-clang compiler directly (matches GitHub workflow)
find_program(MOS_C64_CLANG mos-c64-clang
    HINTS /opt/llvm-mos/bin
    REQUIRED
)

# Set as C compiler before project()
set(CMAKE_C_COMPILER ${MOS_C64_CLANG})
set(CMAKE_C_COMPILER_WORKS 1)  # Skip compiler test for cross-compilation

project(c64_spellcheck C)

# Set C standard
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Step 1: Generate Bloom filter and config header (mirrors GitHub workflow)
add_custom_command(
    OUTPUT ${CMAKE_SOURCE_DIR}/build/generated/bloom_config.h
           ${CMAKE_SOURCE_DIR}/build/generated/bloom.dat
    COMMAND ${CMAKE_COMMAND} -E echo "Generating Bloom filter..."
    COMMAND python3 ${CMAKE_SOURCE_DIR}/src/python/build_bloom.py
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    COMMENT "Building Bloom filter data"
)

# Step 2: Compile C64 program (mirrors: mos-c64-clang -Os -Ibuild/generated ...)
add_executable(spellcheck
    src/spellcheck.c
    ${CMAKE_SOURCE_DIR}/build/generated/bloom_config.h
)

# Include generated header directory
target_include_directories(spellcheck PRIVATE
    ${CMAKE_SOURCE_DIR}/build/generated
)

# Compiler flags matching GitHub workflow
target_compile_options(spellcheck PRIVATE
    -Os      # Optimize for size
    -flto    # Enable link-time optimization
)

# Set output to artifacts directory
set_target_properties(spellcheck PROPERTIES
    OUTPUT_NAME "spellcheck"
    SUFFIX ".prg"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/build/artifacts"
)

# Step 3: Create disk image after build (mirrors second build_bloom.py call)
add_custom_command(TARGET spellcheck POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E echo "Creating disk image..."
    COMMAND python3 ${CMAKE_SOURCE_DIR}/src/python/build_bloom.py
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    COMMENT "Creating C64 disk image"
)
