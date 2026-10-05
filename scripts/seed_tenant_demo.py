"""Seeds two orgs' worth of demo data for manually testing tenant isolation.

Gives the existing seeded org (from seed_dev.py) and a second org, "Spice
Route Caterers", each a vendor, a client, a project, a subproject and an
invoice, then prints every id so they can be pasted into Postman.

    DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/madras_menu_local \
        env/bin/python scripts/seed_tenant_demo.py

Run seed_dev.py first. The second org's vendor password is read from
SEED_VENDOR_PASSWORD, or prompted for. Refuses to run twice.
"""
import getpass
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from auth.security import hash_password  # noqa: E402
from database import SessionLocal  # noqa: E402
from models import Invoice, Organization, Project, Subproject, User  # noqa: E402
from services.invoices import compute_invoice_amount  # noqa: E402

# demo orgs use the default org timezone, so event times are local to it
EASTERN = ZoneInfo("America/New_York")

ORG_B_VENDOR_EMAIL = "vendor.b@spiceroute.example"


def _client(db, org_id, name, email):
    client = User(
        fullName=name, userEmail=email, userPhoneNumber="5550000001",
        preferredContact="email", userRole="client", userOrg=org_id,
    )
    db.add(client)
    db.flush()
    return client


def _project_tree(db, org_id, vendor, client, name):
    """A project with the client linked, one subproject and one invoice."""
    project = Project(
        projectName=name, projectStatus="Proposal",
        projectStartDate=datetime(2026, 12, 5, 18, tzinfo=EASTERN), projectEndDate=datetime(2026, 12, 5, 23, tzinfo=EASTERN),
        vendorOnProject=vendor.userId, organizationId=org_id,
    )
    project.users.append(client)
    db.add(project)
    db.flush()

    subproject = Subproject(
        subprojectName=f"{name}: reception", projectAssociatedTo=project.projectId,
        cuisine=["South Indian"], religion="Hindu", subprojectDate=datetime(2026, 12, 5, 19, tzinfo=EASTERN),
        guestCount=120, subprojectType="Buffet", subprojectVenue="Hotel",
        subprojectEvent="Wedding Dinner",
    )
    db.add(subproject)
    db.flush()

    invoice = Invoice(
        invoiceStatus="Generated", totalAmount=10000.0, depositPercentage=25,
        invoiceAmount=compute_invoice_amount(10000.0, 25),
        invoiceAssignedTo=client.userId, projectAssociatedTo=project.projectId,
        subprojectId=subproject.subprojectId,
    )
    db.add(invoice)
    db.flush()
    return project, subproject, invoice


def main() -> None:
    db = SessionLocal()
    try:
        if db.execute(select(User).where(User.userEmail == ORG_B_VENDOR_EMAIL)).scalars().first():
            sys.exit("Demo data already seeded; nothing to do.")

        vendor_a = db.execute(select(User).where(User.userRole == "vendor")).scalars().first()
        if vendor_a is None:
            sys.exit("No vendor found. Run scripts/seed_dev.py first.")
        org_a = db.get(Organization, vendor_a.userOrg)

        password = os.environ.get("SEED_VENDOR_PASSWORD") or getpass.getpass(f"Password for {ORG_B_VENDOR_EMAIL}: ")
        if not password:
            sys.exit("A password is required.")

        org_b = Organization(orgName="Spice Route Caterers", orgEmail="hello@spiceroute.example", orgDisabled=False)
        db.add(org_b)
        db.flush()
        vendor_b = User(
            fullName="Vendor B", userEmail=ORG_B_VENDOR_EMAIL, userPhoneNumber="5550000002",
            preferredContact="email", userRole="vendor", userOrg=org_b.orgId,
            passwordHash=hash_password(password),
        )
        db.add(vendor_b)
        db.flush()

        client_a = _client(db, org_a.orgId, "Asha Sharma", "asha.client@example.com")
        client_b = _client(db, org_b.orgId, "Ravi Iyer", "ravi.client@example.com")
        a = _project_tree(db, org_a.orgId, vendor_a, client_a, "Sharma Wedding")
        b = _project_tree(db, org_b.orgId, vendor_b, client_b, "Iyer Reception")
        db.commit()

        for label, org, vendor, client, (project, subproject, invoice) in (
            ("Org A", org_a, vendor_a, client_a, a),
            ("Org B", org_b, vendor_b, client_b, b),
        ):
            print(f"\n{label}: {org.orgName}")
            print(f"  org_id        {org.orgId}")
            print(f"  vendor login  {vendor.userEmail}")
            print(f"  client        {client.userId}  ({client.userEmail})")
            print(f"  project       {project.projectId}")
            print(f"  subproject    {subproject.subprojectId}")
            print(f"  invoice       {invoice.invoiceId}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
