@echo off
setlocal
call "C:\Program Files\Microsoft Visual Studio\18\Insiders\VC\Auxiliary\Build\vcvars32.bat"
if errorlevel 1 exit /b 1
cd /d "%~dp0"
cl /nologo /O2 /MT /EHsc /W3 /LD version_proxy.cpp /Fe:version.dll /link /DEF:version.def user32.lib gdi32.lib kernel32.lib
if errorlevel 1 exit /b 1
echo Build succeeded: %cd%\version.dll
