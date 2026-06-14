# Start the FastAPI server locally
# Ensure you are in the virtual environment if you use one

# Check if .env exists, if not, copy from .env.example
if (!(Test-Path ".env")) {
    Write-Host "No .env file found. Creating one from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" -Destination ".env"
    Write-Host "Please remember to update the GEMINI_API_KEY in the .env file!" -ForegroundColor Cyan
}

Write-Host "Starting the backend and frontend at http://127.0.0.1:8000" -ForegroundColor Green
python -m uvicorn app.main:app --reload
