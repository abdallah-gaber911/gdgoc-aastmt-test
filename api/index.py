import os

# Set DATABASE_URL fallback for serverless execution environment
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = (
        "postgresql://platform_user.iaujdszxrgmvfjrwokhy:GdgocAASTMT2026_SecurePass!@aws-0-eu-central-1.pooler.supabase.com:6543/postgres?sslmode=require"
    )

from app.main import app
