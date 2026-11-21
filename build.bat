@echo off
rem Builds dist\Launcher.exe. Copy launcher_config.json next to the .exe.
rem Uses "python -m" so it works even if Python's Scripts folder is not on PATH.
python -m pip install -r requirements.txt pyinstaller || goto :fail
python -m PyInstaller --noconfirm Launcher.spec || goto :fail
echo.
echo Done: dist\Launcher.exe
goto :end

:fail
echo.
echo Build FAILED (see the error above).

:end
rem Keep the window open when launched by double-click.
pause
