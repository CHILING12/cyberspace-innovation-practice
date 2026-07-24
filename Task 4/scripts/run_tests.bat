@echo off
setlocal
cd /d "%~dp0\.."
if not exist build\test_vectors.exe (
  echo Build first: scripts\build.bat
  exit /b 1
)
build\test_vectors.exe || exit /b 1
build\test_impl.exe || exit /b 1
build\test_random.exe || exit /b 1
if exist build\test_mb.exe (
  build\test_mb.exe || exit /b 1
)
echo ALL TESTS PASSED
endlocal
