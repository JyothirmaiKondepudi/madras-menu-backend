"""Adds billing demo data on top of scripts/seed_tenant_demo.py.

Each demo project ("Sharma Wedding" in Org A, "Iyer Reception" in Org B)
gets a second subproject with its own invoice, and payments are recorded
through services.billing_history.record_payment, so billing_history and
billing_info are filled exactly as the API would fill them.

    DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/madras_menu_local \
        env/bin/python scripts/seed_billing_demo.py

Refuses to run twice.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from database import SessionLocal  # noqa: E402
from models import BillingHistory, BillingInfo, Invoice, Organization, Project, Subproject  # noqa: E402
from services.billing_history import record_payment  # noqa: E402
from services.invoices import compute_invoice_amount  # noqa: E402

# project -> payments (in cents) for its existing reception invoice and the new mehendi invoice
PLAN = {
    "Sharma Wedding": {"reception": [100000], "mehendi": [150000]},  # partial, paid in full
    "Iyer Reception": {"reception": [250000], "mehendi": [50000]},   # paid in full, partial
}


def _add_mehendi(db, project):
    subproject = Subproject(
        subprojectName=f"{project.projectName}: mehendi", projectAssociatedTo=project.projectId,
        cuisine=["North Indian"], religion="Hindu", subprojectDate=datetime(2026, 12, 4, 18),
        guestCount=60, subprojectType="Live Stations", subprojectVenue="Home", subprojectEvent="mehendi",
    )
    db.add(subproject)
    db.flush()
    client = project.users[0]
    invoice = Invoice(
        invoiceStatus="Generated", totalAmount=6000.0, depositPercentage=25,
        invoiceAmount=compute_invoice_amount(6000.0, 25),
        invoiceAssignedTo=client.userId, projectAssociatedTo=project.projectId,
        subprojectId=subproject.subprojectId,
    )
    db.add(invoice)
    db.commit()
    return subproject, invoice


def main() -> None:
    db = SessionLocal()
    try:
        projects = {
            p.projectName: p
            for p in db.execute(select(Project).where(Project.projectName.in_(PLAN))).scalars()
        }
        missing = set(PLAN) - set(projects)
        if missing:
            sys.exit(f"Missing demo projects {sorted(missing)}. Run scripts/seed_tenant_demo.py first.")

        project_ids = [p.projectId for p in projects.values()]
        already = db.execute(
            select(BillingHistory.id)
            .join(Invoice, BillingHistory.invoiceId == Invoice.invoiceId)
            .where(Invoice.projectAssociatedTo.in_(project_ids))
        ).first()
        if already:
            sys.exit("Billing demo data already seeded; nothing to do.")

        for name, payments in PLAN.items():
            project = projects[name]
            reception_invoice = db.execute(
                select(Invoice).where(Invoice.projectAssociatedTo == project.projectId)
            ).scalars().first()
            reception_sub = db.get(Subproject, reception_invoice.subprojectId)
            mehendi_sub, mehendi_invoice = _add_mehendi(db, project)

            org = db.get(Organization, project.organizationId)
            print(f"\n{org.orgName} / {name}  (project {project.projectId})")
            for label, sub, invoice in (
                ("reception", reception_sub, reception_invoice),
                ("mehendi", mehendi_sub, mehendi_invoice),
            ):
                for cents in payments[label]:
                    entry = record_payment(invoice, amount=cents, occurred_at=None,
                                           billing_metadata={"note": "demo seed"}, db=db)
                info = db.get(BillingInfo, sub.subprojectId)
                print(f"  {label:<9} subproject {sub.subprojectId}")
                print(f"            invoice    {invoice.invoiceId}  (due ${invoice.invoiceAmount:,.2f})")
                print(f"            payment    {entry.id}  (${cents / 100:,.2f})")
                print(f"            status     {info.status}, balance ${info.balanceDue:,.2f}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
