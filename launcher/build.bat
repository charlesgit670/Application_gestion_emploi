@echo off
rem Compile le lanceur JobFinder.exe a la racine du projet.
rem Utilise le compilateur C# fourni avec Windows (.NET Framework 4) : rien a installer.
set CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe
"%CSC%" /nologo /target:exe /codepage:65001 /out:"%~dp0..\JobFinder.exe" "%~dp0JobFinder.cs"
