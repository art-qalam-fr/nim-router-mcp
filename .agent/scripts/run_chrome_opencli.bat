@echo off
REM ============================================================
REM  Lance Chrome avec l'extension OpenCLI Browser Bridge chargee.
REM  Requis pour tout outil "session navigateur" (OpenCLI) :
REM    opencli doctor doit afficher "Extension: connected".
REM  Injecte par Hephaistos-Kit — ne pas deplacer hors .agent/scripts/.
REM ============================================================
setlocal

set "EXT=%USERPROFILE%\.opencli\extension"
if not exist "%EXT%\manifest.json" (
    echo [ERREUR] Extension OpenCLI introuvable : %EXT%
    echo          Installer : npm i -g @jackwener/opencli
    pause
    exit /b 1
)

set "CHROME=<HEPHAISTOS_ROOT>\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=<HEPHAISTOS_ROOT> (x86)\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" (
    echo [ERREUR] chrome.exe introuvable aux emplacements standards.
    pause
    exit /b 1
)

start "" "%CHROME%" --load-extension="%EXT%"
echo Chrome lance avec l'extension OpenCLI (%EXT%).
echo Verifier : opencli doctor  -^>  "Extension: connected"
endlocal
