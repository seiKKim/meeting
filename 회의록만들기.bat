@echo off
chcp 65001 >nul
REM 사용법 1) 그냥 더블클릭  -> "회의록" 폴더의 모든 녹음을 일괄 처리
REM 사용법 2) 녹음 파일을 이 배치파일에 드래그&드롭 -> 그 파일만 처리
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" meeting.py %*
echo.
echo 완료. 창을 닫으려면 아무 키나 누르세요.
pause
