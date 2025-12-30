@echo off
chcp 65001
call .venv\Scripts\activate.bat
echo Running Pylint on git tracked files...
powershell -Command "pylint (git ls-files '*.py')"
pause
