import os
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

if not SUPABASE_KEY:
    print("⚠️ WARNING: SUPABASE_KEY is missing in your .env file!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)