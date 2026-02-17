@echo off
echo ============================================
echo   ELOD - Rating ELO para Scrabble Duplicada
echo ============================================
echo.
"%~dp0elod.exe" --data-path "%~dp0data" --output-path "%~dp0output"
echo.
echo Proceso completado. Los resultados estan en la carpeta "output".
pause
