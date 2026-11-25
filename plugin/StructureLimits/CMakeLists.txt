cmake_minimum_required(VERSION 3.20)
project(ARKLANDStructureLimitsCore LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(StructureLimitsCore STATIC
    src/StructureLimitsCore.cpp
    src/DurableOutbox.cpp
    src/LocalSnapshotStore.cpp
    src/OutboxSynchronizer.cpp
    src/StructureLimitsConfig.cpp
)
target_include_directories(StructureLimitsCore PUBLIC
    src
    ../CustomShop/ArkServerAPI/version/Core/Public
)
if(MSVC)
    target_compile_options(StructureLimitsCore PRIVATE /W4 /permissive-)
else()
    target_compile_options(StructureLimitsCore PRIVATE -Wall -Wextra -Wpedantic)
endif()

include(CTest)
if(BUILD_TESTING)
    find_package(Threads REQUIRED)
    add_executable(StructureLimitsCoreTests tests/core_tests.cpp)
    target_link_libraries(StructureLimitsCoreTests PRIVATE StructureLimitsCore Threads::Threads)
    if(MSVC)
        target_compile_options(StructureLimitsCoreTests PRIVATE /UNDEBUG)
    else()
        target_compile_options(StructureLimitsCoreTests PRIVATE -UNDEBUG)
    endif()
    add_test(NAME StructureLimitsCoreTests COMMAND StructureLimitsCoreTests)
endif()
