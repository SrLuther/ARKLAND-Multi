cmake_minimum_required(VERSION 3.20)
project(CustomShop LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── ArkApi SDK path ───────────────────────────────────────────────
# Set ARKAPI_DIR to the root of the ArkServerAPI SDK clone, e.g.:
#   cmake -DARKAPI_DIR="C:/ArkServerAPI" ..
# Or set the ARKAPI_DIR environment variable.
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

# ── Source files ──────────────────────────────────────────────────
set(SOURCES
    src/Main.cpp
    src/ShopBridge.cpp
    src/ShopConfig.cpp
    src/ShopData.cpp
    src/ShopPerms.cpp
    src/ShopPoints.cpp
    src/ShopStore.cpp
    src/ShopVip.cpp
    src/ShopEntitlements.cpp
    src/TimedPoints.cpp
    src/Commands.cpp
    src/HttpClient.cpp
    src/ShopCloudInventory.cpp
    src/ShopCryoDino.cpp
    src/ShopCryoReader.cpp
    src/ShopMarket.cpp
)

add_library(CustomShop SHARED ${SOURCES})

# ── ArkApi include + import lib (suporta layouts comuns do SDK) ───
set(ARKAPI_INCLUDE_DIRS
    "${ARKAPI_DIR}/version/Core/Public"
    "${ARKAPI_DIR}"
)
set(ARKAPI_LIB "")
foreach(_lib_dir IN ITEMS "${ARKAPI_DIR}/out_lib" "${ARKAPI_DIR}/lib")
    if(EXISTS "${_lib_dir}/ArkApi.lib")
        set(ARKAPI_LIB "${_lib_dir}/ArkApi.lib")
        break()
    endif()
endforeach()
if(NOT ARKAPI_LIB)
    message(FATAL_ERROR "ArkApi.lib not found under ${ARKAPI_DIR}/out_lib or ${ARKAPI_DIR}/lib")
endif()

target_include_directories(CustomShop PRIVATE
    src
    ${ARKAPI_INCLUDE_DIRS}
)

# ── Link libraries ────────────────────────────────────────────────
find_package(nlohmann_json CONFIG REQUIRED)
find_package(unofficial-libmysql CONFIG REQUIRED)

target_link_libraries(CustomShop PRIVATE
    "${ARKAPI_LIB}"
    nlohmann_json::nlohmann_json
    unofficial::libmysql::libmysql
    winhttp.lib
)

# ── Compiler definitions ──────────────────────────────────────────
target_compile_definitions(CustomShop PRIVATE
    WIN32
    _WINDOWS
    _USRDLL
    UNICODE
    _UNICODE
)

# ── Output ────────────────────────────────────────────────────────
set_target_properties(CustomShop PROPERTIES
    OUTPUT_NAME "CustomShop"
    SUFFIX      ".dll"
    PREFIX      ""                 # no "lib" prefix on Windows
)

# ── Deploy config to output dir after build ───────────────────────
add_custom_command(TARGET CustomShop POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${CMAKE_SOURCE_DIR}/configs/config.json"
        "$<TARGET_FILE_DIR:CustomShop>/config.json"
    COMMENT "Copying config.json to output directory"
)
