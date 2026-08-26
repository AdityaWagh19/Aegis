# scripts/set_tenant_razorpay.py
"""
Usage: python scripts/set_tenant_razorpay.py --tenant-id t_123 --key-id rzp_test_xxx --key-secret yyy --webhook-secret zzz
Encrypts Razorpay API keys and webhook secrets and stores them for the specified tenant.
"""
import asyncio
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select
from models.tenant import encrypt, hash_api_key
from models.db import AsyncSessionLocal, TenantORM, init_db


async def set_credentials(tenant_id: str, key_id: str, key_secret: str, webhook_secret: str):
    await init_db()
    async with AsyncSessionLocal() as db:
        tenant = (await db.execute(select(TenantORM).where(TenantORM.tenant_id == tenant_id))).scalars().first()
        if not tenant:
            print(f"Error: Tenant '{tenant_id}' not found.")
            return

        tenant.razorpay_key_id_enc = encrypt(key_id)
        tenant.razorpay_key_secret_enc = encrypt(key_secret)
        tenant.razorpay_webhook_secret_enc = encrypt(webhook_secret)
        tenant.razorpay_webhook_secret_hash = hash_api_key(webhook_secret)
        await db.commit()
        print(f"Razorpay credentials configured successfully for tenant '{tenant_id}'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--key-secret", required=True)
    parser.add_argument("--webhook-secret", required=True)
    args = parser.parse_args()
    asyncio.run(set_credentials(args.tenant_id, args.key_id, args.key_secret, args.webhook_secret))
