from __future__ import annotations

import argparse

from app.auth.jwt import create_access_token
from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a demo tenant-scoped JWT.")
    parser.add_argument("--tenant-id", default="demo")
    parser.add_argument("--subject", default="demo-user")
    args = parser.parse_args()
    print(
        create_access_token(
            subject=args.subject,
            tenant_id=args.tenant_id,
            settings=get_settings(),
        )
    )


if __name__ == "__main__":
    main()
