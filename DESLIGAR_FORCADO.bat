@echo off
echo DERRUBANDO O SISTEMA...
taskkill /F /IM python.exe
taskkill /F /IM streamlit.exe
echo.
echo SISTEMA DESLIGADO COM SUCESSO.
pause