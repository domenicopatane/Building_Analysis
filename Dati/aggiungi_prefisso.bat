@echo off
REM Rinominare ogni file IT.NISXX..*.mseed aggiungendo SYY_ davanti

REM --- Definisci la mappa NIS → Sxx qui sotto ---
set NIS21=S01
set NIS22=S02
set NIS23=S03
set NIS24=S04
set NIS25=S05
REM aggiungi eventualmente altre corrispondenze

REM --- Loop su tutti i file IT.NIS*.mseed ---
for %%f in (IT.NIS*.mseed) do (
    setlocal enabledelayedexpansion
    set "oldname=%%f"
    set "newname="
    REM --- Cicla sulle corrispondenze NISxx ---
    for %%N in (21 22 23 24 25) do (
        echo %%f | findstr /C:"NIS%%N" >nul
        if !errorlevel! == 0 (
            set "label=!NIS%%N!"
            set "newname=!label!_%%f"
        )
    )
    if not "!newname!"=="" (
        ren "!oldname!" "!newname!"
        echo Rinominato: !oldname! → !newname!
    )
    endlocal
)
echo Operazione completata!
pause