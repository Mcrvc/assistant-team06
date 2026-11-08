import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# =========================================
# 1. ENVIRONMENT CONFIGURATION
# =========================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

# =========================================
# 2. FASTAPI APPLICATION
# =========================================

app = FastAPI(title="Yourin API")

# =========================================
# 3. CORS CONFIGURATION
# =========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================
# 4. PUBLIC APPLICATION CONFIGURATION
# =========================================

@app.get("/api/config")
async def get_public_config():
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY")

    if not supabase_url or not supabase_publishable_key:
        raise HTTPException(
            status_code=500,
            detail="Supabase configuration is missing."
        )

    return {
        "supabaseUrl": supabase_url,
        "supabasePublishableKey": supabase_publishable_key
    }