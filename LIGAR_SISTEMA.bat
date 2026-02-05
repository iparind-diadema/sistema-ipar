@echo off
TITLE SERVIDOR IPAR
cd /d "%~dp0"
echo INICIANDO SISTEMA...
echo ACESSE PELO TABLET EM:
ipconfig | findstr "IPv4"
echo :8501
echo.
streamlit run main.py --server.address=192.168.0.251
pause