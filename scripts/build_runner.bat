@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul
set PATH=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin;C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja;%PATH%
cd /d D:\Drakengard_Recomp\PS2Recomp
cmake -S . -B out\build-fast -G Ninja -DCMAKE_BUILD_TYPE=Fast "-DCMAKE_CXX_FLAGS_FAST=/O2 /Ob1 /DNDEBUG /arch:AVX2 /MD" "-DCMAKE_C_FLAGS_FAST=/O2 /DNDEBUG /MD" -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL -DPS2X_BUILD_TEST=OFF -DPS2X_BUILD_STUDIO=OFF -DPS2X_BUILD_RECOMP=OFF -DPS2X_BUILD_ANALYZER=OFF -DPS2X_ENABLE_AGRESSIVE_LOGS=OFF -DPS2X_ENABLE_IOP_RPC_TRACE=OFF "-DCMAKE_EXE_LINKER_FLAGS_FAST=/MAP" || exit /b 1
cmake --build out\build-fast --target ps2EntryRunner -j 15 || exit /b 1
