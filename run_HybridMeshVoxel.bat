@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM 一键打开 plan5 HybridMeshVoxel 调试入口
REM 用法：
REM   run_HybridMeshVoxel.bat
REM   run_HybridMeshVoxel.bat cornell
REM   run_HybridMeshVoxel.bat "E:\path\to\scene.pyscene" voxelrouteid far
REM   run_HybridMeshVoxel.bat "E:\path\to\scene.pyscene" composite near ForceMeshPipeline

set "MOGWAI=E:\GraduateDesign\Falcor_Cp\build\windows-vs2022\bin\Release\Mogwai.exe"
set "SCRIPT=E:\GraduateDesign\Falcor_Cp\scripts\Voxelization_HybridMeshVoxel.py"
set "DEFAULT_SCENE=E:\GraduateDesign\Falcor_Cp\Scene\Arcade\Arcade.pyscene"
set "ARCADE_CACHE=E:\GraduateDesign\Falcor_Cp\resource\Arcade_(256, 171, 256)_256.bin_CPU"

if "%~1"=="" (
    set "SCENE=%DEFAULT_SCENE%"
) else (
    if /i "%~1"=="cornell" (
        set "SCENE=E:\GraduateDesign\Falcor_Cp\Scene\Box\CornellBox.pyscene"
    ) else (
        set "SCENE=%~1"
    )
)

if "%~2"=="" (
    set "HYBRID_OUTPUT_MODE=composite"
) else (
    set "HYBRID_OUTPUT_MODE=%~2"
)

if "%~3"=="" (
    set "HYBRID_REFERENCE_VIEW=near"
) else (
    set "HYBRID_REFERENCE_VIEW=%~3"
)

if "%~4"=="" (
    set "HYBRID_EXECUTION_MODE=ByObjectRoute"
) else (
    set "HYBRID_EXECUTION_MODE=%~4"
)

for %%I in ("%SCENE%") do set "HYBRID_SCENE_HINT=%%~nI"
set "HYBRID_SCENE_PATH=%SCENE%"
set "HYBRID_VOXELIZATION_BACKEND=CPU"
set "HYBRID_HIDE_UI=0"
set "HYBRID_OPEN_PROFILER=1"
set "HYBRID_FRAMEBUFFER_WIDTH=1600"
set "HYBRID_FRAMEBUFFER_HEIGHT=900"
set "HYBRID_CPU_VOXEL_RESOLUTION=256"
set "HYBRID_CPU_SAMPLE_FREQUENCY=256"
set "HYBRID_CPU_AUTO_GENERATE=0"

if not exist "%MOGWAI%" (
    echo Error: Mogwai executable not found:
    echo   %MOGWAI%
    exit /b 1
)

if not exist "%SCRIPT%" (
    echo Error: Hybrid script not found:
    echo   %SCRIPT%
    exit /b 1
)

if not exist "%SCENE%" (
    echo Error: Scene not found:
    echo   %SCENE%
    exit /b 1
)

if /i "%HYBRID_SCENE_HINT%"=="Arcade" (
    if not exist "!ARCADE_CACHE!" (
        set "HYBRID_CPU_AUTO_GENERATE=1"
        echo Warning: Arcade CPU cache is missing.
        echo          This launch will regenerate the cache at:
        echo          !ARCADE_CACHE!
        echo          Relaunch once after generation finishes to validate the new cache content.
        echo.
    )
)

echo Starting Mogwai (HybridMeshVoxel)...
echo   Script: %SCRIPT%
echo   Scene:  %SCENE%
echo   Hint:   %HYBRID_SCENE_HINT%
echo   Mode:   %HYBRID_OUTPUT_MODE%
echo   View:   %HYBRID_REFERENCE_VIEW%
echo   Execution: %HYBRID_EXECUTION_MODE%
echo   Backend: %HYBRID_VOXELIZATION_BACKEND%
echo   Profiler: %HYBRID_OPEN_PROFILER%
echo   AutoGenerate: %HYBRID_CPU_AUTO_GENERATE%
echo   GUI switch: use Mogwai Graphs dropdown to select ByObjectRoute / MeshOnly / VoxelOnly
echo.

"%MOGWAI%" --script "%SCRIPT%" --scene "%SCENE%" --width=1600 --height=900
exit /b %errorlevel%
