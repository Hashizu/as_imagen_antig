@echo off
chcp 65001
call .venv\Scripts\activate.bat
streamlit run app.py
pause
