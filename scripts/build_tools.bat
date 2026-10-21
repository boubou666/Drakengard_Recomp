@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul
set PATH=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin;C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja;%PATH%
cd /d D:\Drakengard_Recomp\PS2Recomp
cmake -S . -B out\build -G Ninja -DCMAKE_BUILD_TYPE=Release -DPS2X_BUILD_TEST=OFF -DPS2X_BUILD_STUDIO=OFF || exit /b 1
cmake --build out\build --target ps2_recomp ps2_analyzer || exit /b 1
