@echo off
cd /d "d:\02_Non-Medicine\01_Coding\01_studyagent\exam_manager"
call .venv\Scripts\activate
echo Exam Manager를 시작합니다...
start http://127.0.0.1:5000
python run.py
pause
