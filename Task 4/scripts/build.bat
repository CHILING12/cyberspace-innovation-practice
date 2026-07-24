@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

set "VCVARS="
if exist "%ProgramFiles%\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" (
  set "VCVARS=%ProgramFiles%\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
)
if exist "%ProgramFiles%\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" (
  set "VCVARS=%ProgramFiles%\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
)
if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat" (
  set "VCVARS=%ProgramFiles(x86)%\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"
)

if not defined VCVARS (
  echo [ERROR] vcvars64.bat not found. Install VS with C++ desktop workload.
  exit /b 1
)

echo Using: %VCVARS%
call "%VCVARS%" || exit /b 1

where cmake >nul 2>&1
if errorlevel 1 (
  if exist "%ProgramFiles%\CMake\bin\cmake.exe" set "PATH=%ProgramFiles%\CMake\bin;%PATH%"
)

where cmake >nul 2>&1
if errorlevel 1 (
  echo [ERROR] cmake not in PATH
  exit /b 1
)

where ninja >nul 2>&1
if errorlevel 1 (
  echo [WARN] ninja not found, falling back to Visual Studio generator
  cmake -S . -B build -G "Visual Studio 17 2022" -A x64
  if errorlevel 1 cmake -S . -B build -G "Visual Studio 18 2026" -A x64
  if errorlevel 1 exit /b 1
  cmake --build build --config Release -j
) else (
  cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
  if errorlevel 1 exit /b 1
  cmake --build build -j
)

if errorlevel 1 exit /b 1
echo.
echo Build OK. Run tests:
echo   build\test_vectors.exe
echo   build\test_random.exe
echo   build\test_impl.exe
echo   build\bench_sm3.exe
endlocal
