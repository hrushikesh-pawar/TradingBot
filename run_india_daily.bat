@echo off
title NSE Daily Scanner
cd /d C:\TradingBot
call .\venv\Scripts\activate.bat
python -m bots.run_india_stocks