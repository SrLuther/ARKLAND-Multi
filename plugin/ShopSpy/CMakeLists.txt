cmake_minimum_required(VERSION 3.20)
project(ShopSpy LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── ArkApi SDK path ───────────────────────────────────────────────
if(NOT DEFINED ARKAPI_DIR)
    if(DEFINED ENV{ARKAPI_DIR})
        set(ARKAPI_DIR "$ENV{ARKAPI_DIR}")
    else()
        message(FATAL_ERROR
            "ARKAPI_DIR must point to the ArkServerAPI SDK root.\n"
            "Pass -DARKAPI_DIR=<path> or set the ARKAPI_DIR env var.")
    endif()
endif()

message(STATUS "ArkApi SDK: ${ARKAPI_DIR}")

set(SOURCES
    src/Main.cpp
)

add_library(ShopSpy SHARED ${SOURCES})

target_include_directories(ShopSpy PRIVATE
    src
    "${ARKAPI_DIR}/API"
    "${ARKAPI_DIR}/API/ARK"
)

find_package(nlohmann_json CONFIG REQUIRED)

target_link_libraries(ShopSpy PRIVATE
    "${ARKAPI_DIR}/lib/ArkApi.lib"
    nlohmann_json::nlohmann_json
)

target_compile_definitions(ShopSpy PRIVATE
    WIN32
    _WINDOWS
    _USRDLL
    UNICODE
    _UNICODE
)

target_compile_options(ShopSpy PRIVATE /W3 /permissive-)

set_target_properties(ShopSpy PROPERTIES
    OUTPUT_NAME "ShopSpy"
)
