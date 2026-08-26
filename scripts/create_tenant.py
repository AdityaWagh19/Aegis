# scripts/create_tenant.py
"""
Usage: python scripts/create_tenant.py --name "NBFC Name" --webhook-url https://nbfc.com/aegis/callback
Prints the raw API key (shown once only) and the tenant_id.
"""
import asyncio
import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from models.tenant import encrypt, hash_api_key
from models.db import AsyncSessionLocal, TenantORM, TenantComplianceConfigORM
from models.db import init_db


async def create(name: str, webhook_url: str):
    await init_db()
    raw_api_key = f"aegis_{secrets.token_urlsafe(32)}"
    callback_secret = secrets.token_urlsafe(32)
    tenant = TenantORM(
        name=name,
        api_key_hash=hash_api_key(raw_api_key),
        webhook_url=webhook_url,
        callback_secret=encrypt(callback_secret),
    )
    config = TenantComplianceConfigORM(tenant_id=tenant.tenant_id)
    async with AsyncSessionLocal() as db:
        db.add(tenant)
        db.add(config)
        await db.commit()

    print(f"\nTenant created successfully.")
    print(f"  Tenant ID:       {tenant.tenant_id}")
    print(f"  Name:            {name}")
    print(f"  API Key:         {raw_api_key}  (save this — shown once only)")
    print(f"  Callback Secret: {callback_secret}  (save this — shown once only)")
    print(f"\nConfigure the NBFC's Razorpay key by calling:")
    print(f"  python scripts/set_tenant_razorpay.py --tenant-id {tenant.tenant_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--webhook-url", required=True)
    args = parser.parse_args()
    asyncio.run(create(args.name, args.webhook_url))
