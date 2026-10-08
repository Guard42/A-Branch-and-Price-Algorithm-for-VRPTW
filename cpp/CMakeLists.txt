cmake_minimum_required(VERSION 3.15)
project(bpvrptw_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(bpvrptw_core STATIC
    src/instance.cpp
    src/route.cpp
    src/pricing.cpp
    src/simplex.cpp
    src/construction.cpp
    src/column_generation.cpp
    src/branch_and_price.cpp
)
target_include_directories(bpvrptw_core PUBLIC src)

if(MSVC)
    target_compile_options(bpvrptw_core PRIVATE /O2 /W3 /permissive-)
    target_compile_options(bpvrptw_core PRIVATE /utf-8)
else()
    target_compile_options(bpvrptw_core PRIVATE -O3 -Wall -Wextra)
endif()

add_executable(bpvrptw_cpp src/main.cpp)
target_link_libraries(bpvrptw_cpp PRIVATE bpvrptw_core)

add_executable(bpvrptw_cpp_test src/smoke_test.cpp)
target_link_libraries(bpvrptw_cpp_test PRIVATE bpvrptw_core)

enable_testing()
# The bundled dataset lives one level above cpp/.
add_test(NAME known_optima
         COMMAND bpvrptw_cpp_test ${CMAKE_CURRENT_SOURCE_DIR}/../dataset)
