@echo off
rem Gera dist\Launcher.exe. Copie o launcher_config.json para a mesma pasta do .exe.
pip install -r requirements.txt pyinstaller || exit /b 1
pyinstaller --noconfirm Launcher.spec || exit /b 1
echo.
echo Pronto: dist\Launcher.exe
