"""Creates the platform's own org and its first platform admin.

Only a platform admin can create orgs or other platform admins, so the very
first one has to be inserted directly. This is a one-time bootstrap: once a
platform admin exists, create further admins through POST /users instead.

    DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/madras_menu_local \
        env/bin/python scripts/seed_platform_admin.py --admin-email you@yourcompany.com

The admin's password is read from SEED_ADMIN_PASSWORD, or prompted for.
"""
import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from auth.security import hash_password  # noqa: E402
from database import SessionLocal  # noqa: E402
from models import Organization, User  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--org-name", default="Madras Menu Studio (platform)")
    parser.add_argument("--org-email", default="platform@madrasmenustudio.example")
    parser.add_argument("--admin-name", default="Platform Admin")
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-phone", default="5550000009")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if db.execute(select(User).where(User.userRole == "platform_admin")).scalars().first():
            sys.exit("A platform admin already exists; create more through POST /users.")
        if db.execute(select(User).where(User.userEmail == args.admin_email)).scalars().first():
            sys.exit(f"A user with email {args.admin_email} already exists; nothing to do.")

        password = os.environ.get("SEED_ADMIN_PASSWORD") or getpass.getpass("Platform admin password: ")
        if not password:
            sys.exit("A password is required.")

        # the admin needs an org, so the org goes in first
        org = Organization(orgName=args.org_name, orgEmail=args.org_email, orgDisabled=False)
        db.add(org)
        db.flush()

        admin = User(
            fullName=args.admin_name,
            userEmail=args.admin_email,
            userPhoneNumber=args.admin_phone,
            preferredContact="email",
            userRole="platform_admin",
            userOrg=org.orgId,
            passwordHash=hash_password(password),
        )
        db.add(admin)
        db.commit()
        print(f"Created org '{org.orgName}' ({org.orgId}) and platform admin {admin.userEmail} ({admin.userId}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
