@echo off
echo Installing required Python packages...
pip install -r requirements.txt

echo.
echo Cleaning up old build files...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo Building executable with PyInstaller...
pyinstaller audio_duplicate_finder.spec

echo.
echo Build complete! The executable is now windowed (no console window).
echo Check the 'dist' folder for your executable.
pause