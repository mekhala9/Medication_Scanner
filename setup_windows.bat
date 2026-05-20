@echo off
echo ============================================
echo   MEDICATION SCANNER — Windows Setup
echo ============================================
echo.
echo [1/3] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate
echo.
echo [2/3] Installing dependencies...
pip install -r requirements.txt
echo.
echo [3/3] Done!
echo.
echo ============================================
echo   NEXT STEPS:
echo ============================================
echo   1. Set your API key:
echo      set OPENAI_API_KEY=sk-your-key-here
echo   2. Run the app:
echo      python app.py
echo   3. Open browser at: http://localhost:5000
echo ============================================
pause
