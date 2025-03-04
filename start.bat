@echo off

echo Starting SLL System...

:: Start backend server
start "Backend Server" cmd /k "cd backend && python main.py"

:: Wait for a moment to ensure backend is up
timeout /t 5

:: Start frontend application
start "Frontend Application" cmd /k "cd frontend && streamlit run app.py"

echo System startup initiated. Please check the opened windows for status.