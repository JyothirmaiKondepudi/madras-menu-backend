"""Creates the first organization and its vendor for local development.

Every user must belong to an org, and creating anything through the API
needs a logged-in vendor, so the first org + vendor have to be inserted
directly. Run once against an empty user_data table:

    DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/madras_menu_local \
        env/bin/python scripts/seed_dev.py --vendor-email you@example.com

The vendor's password is read from SEED_VENDOR_PASSWORD, or prompted for.
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
    parser.add_argument("--org-name", default="Madras Catering")
    parser.add_argument("--org-email", default="hello@madrascatering.example")
    parser.add_argument("--vendor-name", default="Dev Vendor")
    parser.add_argument("--vendor-email", required=True)
    parser.add_argument("--vendor-phone", default="5550000000")
    args = parser.parse_args()

    password = os.environ.get("SEED_VENDOR_PASSWORD") or getpass.getpass("Vendor password: ")
    if not password:
        sys.exit("A password is required.")

    db = SessionLocal()
    try:
        if db.execute(select(User).where(User.userEmail == args.vendor_email)).scalars().first():
            sys.exit(f"A user with email {args.vendor_email} already exists; nothing to do.")

        # the vendor needs an org, so the org goes in first
        org = Organization(orgName=args.org_name, orgEmail=args.org_email, orgDisabled=False)
        db.add(org)
        db.flush()

        vendor = User(
            fullName=args.vendor_name,
            userEmail=args.vendor_email,
            userPhoneNumber=args.vendor_phone,
            preferredContact="email",
            userRole="vendor",
            userOrg=org.orgId,
            passwordHash=hash_password(password),
        )
        db.add(vendor)
        db.commit()
        print(f"Created org '{org.orgName}' ({org.orgId}) and vendor {vendor.userEmail} ({vendor.userId}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
