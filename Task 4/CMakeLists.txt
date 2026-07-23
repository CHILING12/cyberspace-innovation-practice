cmake_minimum_required(VERSION 3.16)
project(sm3-opt C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# --------------------------------------------------------------------------
# Options
# --------------------------------------------------------------------------
option(SM3_BUILD_TESTS "Build correctness tests" ON)
option(SM3_BUILD_BENCH "Build benchmark tool" ON)
option(SM3_ENABLE_AVX2 "Enable AVX2 hybrid (x86_64 only)" ON)
option(SM3_ENABLE_AVX512 "Enable AVX512 hybrid (x86_64 only)" ON)
option(SM3_ENABLE_NEON "Enable NEON hybrid (aarch64 only)" ON)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

# --------------------------------------------------------------------------
# Architecture detection
# --------------------------------------------------------------------------
string(TOLOWER "${CMAKE_SYSTEM_PROCESSOR}" SM3_PROC)
set(SM3_IS_X86 FALSE)
set(SM3_IS_ARM64 FALSE)

if(SM3_PROC MATCHES "^(x86_64|amd64|x64|i[3-6]86)$")
  set(SM3_IS_X86 TRUE)
endif()
if(SM3_PROC MATCHES "^(aarch64|arm64)$")
  set(SM3_IS_ARM64 TRUE)
endif()
# MSVC often reports AMD64 / ARM64 via CMAKE_GENERATOR_PLATFORM
if(CMAKE_GENERATOR_PLATFORM)
  string(TOUPPER "${CMAKE_GENERATOR_PLATFORM}" SM3_GEN_PLAT)
  if(SM3_GEN_PLAT STREQUAL "X64" OR SM3_GEN_PLAT STREQUAL "WIN32")
    set(SM3_IS_X86 TRUE)
  endif()
  if(SM3_GEN_PLAT STREQUAL "ARM64")
    set(SM3_IS_ARM64 TRUE)
    set(SM3_IS_X86 FALSE)
  endif()
endif()

# Host fallback when cross vars are empty (native builds)
if(NOT SM3_IS_X86 AND NOT SM3_IS_ARM64)
  if(CMAKE_HOST_SYSTEM_PROCESSOR MATCHES "AMD64|x86_64|amd64")
    set(SM3_IS_X86 TRUE)
  elseif(CMAKE_HOST_SYSTEM_PROCESSOR MATCHES "ARM64|aarch64|arm64")
    set(SM3_IS_ARM64 TRUE)
  endif()
endif()

# --------------------------------------------------------------------------
# Common sources
# --------------------------------------------------------------------------
set(SM3_COMMON_SOURCES
  src/sm3_common.c
  src/sm3_ref.c
  src/sm3_mb.c
)

if(SM3_IS_X86)
  list(APPEND SM3_COMMON_SOURCES src/x86/cpuid_x86.c)
elseif(SM3_IS_ARM64)
  list(APPEND SM3_COMMON_SOURCES src/arm64/cpu_arm.c)
else()
  # Unknown arch: still provide CPU stubs via x86 file's neon=0 + no AVX
  # Prefer a minimal stub object — compile cpu_arm with forced no-neon if needed.
  message(WARNING "Unknown processor '${CMAKE_SYSTEM_PROCESSOR}'; building ref only")
  list(APPEND SM3_COMMON_SOURCES src/x86/cpuid_x86.c)
endif()

set(SM3_PUBLIC_HEADERS include/sm3.h)

add_library(sm3 STATIC ${SM3_COMMON_SOURCES})
target_include_directories(sm3
  PUBLIC  ${CMAKE_CURRENT_SOURCE_DIR}/include
  PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src
)

if(MSVC)
  target_compile_options(sm3 PRIVATE /W3 /utf-8)
  target_compile_definitions(sm3 PRIVATE _CRT_SECURE_NO_WARNINGS)
else()
  target_compile_options(sm3 PRIVATE -Wall -Wextra -Wno-unused-function)
endif()

# Effective feature flags (arch-gated)
set(SM3_BUILD_AVX2 FALSE)
set(SM3_BUILD_AVX512 FALSE)
set(SM3_BUILD_NEON FALSE)

if(SM3_IS_X86 AND SM3_ENABLE_AVX2)
  set(SM3_BUILD_AVX2 TRUE)
endif()
if(SM3_IS_X86 AND SM3_ENABLE_AVX512)
  set(SM3_BUILD_AVX512 TRUE)
endif()
if(SM3_IS_ARM64 AND SM3_ENABLE_NEON)
  set(SM3_BUILD_NEON TRUE)
endif()

# --------------------------------------------------------------------------
# AVX2 hybrid (x86_64)
# --------------------------------------------------------------------------
if(SM3_BUILD_AVX2)
  add_library(sm3_avx2 OBJECT src/x86/sm3_avx2.c src/x86/sm3_mb_avx2.c)
  target_include_directories(sm3_avx2 PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
  )
  if(MSVC)
    target_compile_options(sm3_avx2 PRIVATE /arch:AVX2 /W3 /utf-8)
    target_compile_definitions(sm3_avx2 PRIVATE _CRT_SECURE_NO_WARNINGS SM3_HAS_AVX2=1)
  else()
    target_compile_options(sm3_avx2 PRIVATE -mavx2 -mfma -Wall -Wextra)
    target_compile_definitions(sm3_avx2 PRIVATE SM3_HAS_AVX2=1)
  endif()
  target_sources(sm3 PRIVATE $<TARGET_OBJECTS:sm3_avx2>)
  target_compile_definitions(sm3 PUBLIC SM3_HAS_AVX2=1)
endif()

# --------------------------------------------------------------------------
# AVX512 hybrid (x86_64)
# --------------------------------------------------------------------------
if(SM3_BUILD_AVX512)
  add_library(sm3_avx512 OBJECT src/x86/sm3_avx512.c)
  target_include_directories(sm3_avx512 PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
  )
  if(MSVC)
    target_compile_options(sm3_avx512 PRIVATE /arch:AVX512 /W3 /utf-8)
    target_compile_definitions(sm3_avx512 PRIVATE _CRT_SECURE_NO_WARNINGS SM3_HAS_AVX512=1)
  else()
    target_compile_options(sm3_avx512 PRIVATE -mavx512f -mavx512bw -mavx512vl -Wall -Wextra)
    target_compile_definitions(sm3_avx512 PRIVATE SM3_HAS_AVX512=1)
  endif()
  target_sources(sm3 PRIVATE $<TARGET_OBJECTS:sm3_avx512>)
  target_compile_definitions(sm3 PUBLIC SM3_HAS_AVX512=1)
endif()

# --------------------------------------------------------------------------
# NEON hybrid (aarch64)
# --------------------------------------------------------------------------
if(SM3_BUILD_NEON)
  add_library(sm3_neon OBJECT src/arm64/sm3_neon.c)
  target_include_directories(sm3_neon PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
  )
  if(MSVC)
    target_compile_options(sm3_neon PRIVATE /W3 /utf-8)
    target_compile_definitions(sm3_neon PRIVATE _CRT_SECURE_NO_WARNINGS SM3_HAS_NEON=1)
  else()
    # NEON is baseline on ARMv8-A 64-bit; keep flags portable for ARM64 toolchains.
    target_compile_options(sm3_neon PRIVATE -Wall -Wextra)
    target_compile_definitions(sm3_neon PRIVATE SM3_HAS_NEON=1)
  endif()
  target_sources(sm3 PRIVATE $<TARGET_OBJECTS:sm3_neon>)
  target_compile_definitions(sm3 PUBLIC SM3_HAS_NEON=1)
endif()

# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------
if(SM3_BUILD_TESTS)
  add_executable(test_vectors tests/test_vectors.c)
  target_link_libraries(test_vectors PRIVATE sm3)

  add_executable(test_random tests/test_random.c)
  target_link_libraries(test_random PRIVATE sm3)

  add_executable(test_impl tests/test_impl.c)
  target_link_libraries(test_impl PRIVATE sm3)

  add_executable(test_mb tests/test_mb.c)
  target_link_libraries(test_mb PRIVATE sm3)

  enable_testing()
  add_test(NAME vectors COMMAND test_vectors)
  add_test(NAME random COMMAND test_random)
  add_test(NAME impl COMMAND test_impl)
  add_test(NAME mb COMMAND test_mb)
endif()

# --------------------------------------------------------------------------
# Benchmark
# --------------------------------------------------------------------------
if(SM3_BUILD_BENCH)
  add_executable(bench_sm3 bench/bench_sm3.c)
  target_link_libraries(bench_sm3 PRIVATE sm3)
endif()

# --------------------------------------------------------------------------
# Install
# --------------------------------------------------------------------------
install(TARGETS sm3 ARCHIVE DESTINATION lib)
install(FILES ${SM3_PUBLIC_HEADERS} DESTINATION include)

message(STATUS "SM3-Opt configuration:")
message(STATUS "  Processor  : ${CMAKE_SYSTEM_PROCESSOR}")
message(STATUS "  Is x86_64  : ${SM3_IS_X86}")
message(STATUS "  Is arm64   : ${SM3_IS_ARM64}")
message(STATUS "  Build type : ${CMAKE_BUILD_TYPE}")
message(STATUS "  AVX2       : ${SM3_BUILD_AVX2}")
message(STATUS "  AVX512     : ${SM3_BUILD_AVX512}")
message(STATUS "  NEON       : ${SM3_BUILD_NEON}")
message(STATUS "  Tests      : ${SM3_BUILD_TESTS}")
message(STATUS "  Bench      : ${SM3_BUILD_BENCH}")
