@echo off
REM ===========================================================================
REM VitalBand — standalone vision demos
REM
REM These run OUTSIDE the dashboard, on purpose. DeepFace needs OpenCV 4.x and
REM the backend runs OpenCV 5.x, so they cannot share one process. Each demo
REM uses the interpreter that has the right stack.
REM
REM   run_demo.bat multi      multi-person fall detection  (backend venv)
REM   run_demo.bat fall       single-person fall detection (backend venv)
REM   run_demo.bat distress   facial distress, one face    (deepface venv)
REM   run_demo.bat faces      facial distress, many faces  (deepface venv)
REM
REM Press q in the video window to quit.
REM ===========================================================================

setlocal
set ROOT=%~dp0..
set BACKEND_PY=%ROOT%\backend\.venv\Scripts\python.exe
set DEEPFACE_PY=%ROOT%\venv-deepface\Scripts\python.exe
set HERE=%~dp0

if "%1"=="" goto usage
if /I "%1"=="multi"    goto multi
if /I "%1"=="fall"     goto fall
if /I "%1"=="distress" goto distress
if /I "%1"=="faces"    goto faces
goto usage

:multi
echo Multi-person fall detection  (tracking up to 4 people)
"%BACKEND_PY%" "%HERE%mediapipe_multiperson_fall.py" %2 %3 %4
goto end

:fall
echo Single-person fall detection
"%BACKEND_PY%" "%HERE%mediapipe_fall.py" %2 %3 %4
goto end

:distress
echo Facial distress detection  (DeepFace, single face)
"%DEEPFACE_PY%" "%HERE%deepface_distress.py" %2 %3 %4
goto end

:faces
echo Facial distress detection  (DeepFace, multiple faces)
"%DEEPFACE_PY%" "%HERE%deepface_distress_multiperson.py" %2 %3 %4
goto end

:usage
echo.
echo   run_demo.bat multi      multi-person fall detection
echo   run_demo.bat fall       single-person fall detection
echo   run_demo.bat distress   facial distress, one face
echo   run_demo.bat faces      facial distress, many faces
echo.
echo   Add --camera 1 if the wrong camera opens.
echo.

:end
endlocal
