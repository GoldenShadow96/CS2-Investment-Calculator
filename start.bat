@echo off
title Uruchamianie CSGO Investment Simulator

:: Uruchom backend Flask (port 5000)
cd end
start cmd /k "py server.py"
cd ..

:: Poczekaj chwilę, aby backend mógł się uruchomić
timeout /t 2 > nul

:: Uruchom frontend (port 8000)
cd front
start cmd /k "py -m http.server 8000"
cd ..

:: Otwórz przeglądarkę
start http://localhost:8000/index.html
