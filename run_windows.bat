@echo off
if not exist .venv (
  py -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
echo Edit .env and set DATABASE_URL, then run this script again.
pause
streamlit run app.py
