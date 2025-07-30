# CS2 Investment Calculator

A browser-based simulator for evaluating and tracking virtual item investments using Steam Market and DMarket pricing strategies.

## Overview

This tool assists players and traders in calculating net profit from buying CS2 skins on DMarket and selling them on the Steam Community Market. It helps determine profitability after deducting all relevant platform fees and allows users to track, ignore, or remove specific transactions.

## How the Investment Strategy Works

1. Acquire items on DMarket at a discounted price.
2. Transfer the item to Steam (after cooldown if needed).
3. Sell it on the Steam Community Market at a higher price.
4. The tool calculates:
   - Realistic Steam revenue after 13% fee.
   - Final profit or loss.
   - Break-even point (the minimum Steam price needed to avoid loss).
5. Users can log, track, and manage transaction history for analysis.

## Project Structure

```
App/
├── front/            # Frontend (HTML, JavaScript)
│   └── index.html
├── end/              # Backend (Flask API)
│   └── server.py
└── run.bat           # Script to launch frontend and backend
```

## Features

- Profit and break-even calculation after fees.
- Persistent transaction history (saved in transactions.json).
- Ability to delete or ignore individual entries.
- Uses Python Flask as backend API.
- Frontend communicates with backend using Fetch API.

## Requirements

- Python 3.7 or newer
- Flask
- Flask-CORS

Install dependencies with:
```
pip install flask flask-cors
```
## Running the Project

### Option 1: Using the provided script (Windows)

1. Run run.bat from the root App directory.
2. This will:
   - Start the Flask backend on port 5000.
   - Start the frontend static server on port 8000.
   - Open the app in your browser.

### Option 2: Manual run

Backend:
```
cd App/end
python server.py
```
or
```
py server.py
```

Frontend:
```
cd App/front
python -m http.server 8000
```
or

```
py -m http.server 8000
```
Then open in browser:

http://localhost:8000/index.html

## File Storage

Transactions are saved to a local file:

App/end/transactions.json

This file is automatically created and updated by the backend.

## Planned Features

- CSV and Excel export
- Graphical analysis and charts
- Search, filter, and tagging support

## Disclaimer

This tool is intended for educational and utility purposes only. It does not provide financial advice or guarantee profit. Virtual item markets are volatile and speculative.
