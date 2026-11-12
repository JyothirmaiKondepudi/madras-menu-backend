"""BE-23: invoices are only ever loaded by id through get_live_invoice.

db.get(Invoice, ...) can return a soft-deleted invoice that is already loaded
in the session (it skips the database, and with it the global soft-delete
filter), so any other call is a chance to leak a deleted invoice."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_CODE = ["routes", "services", "auth", "embeddings", "hierarchy"]
ALLOWED = {("services/invoices.py", "get_live_invoice")}


def _raw_invoice_gets():
    """(file, enclosing function, line) of every <something>.get(Invoice, ...)"""
    found = []
    for folder in APP_CODE:
        for path in sorted((ROOT / folder).rglob("*.py")):
            tree = ast.parse(path.read_text(), filename=str(path))
            for func in ast.walk(tree):
                if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for node in ast.walk(func):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "get"
                        and node.args
                        and isinstance(node.args[0], ast.Name)
                        and node.args[0].id == "Invoice"
                    ):
                        rel = path.relative_to(ROOT).as_posix()
                        found.append((rel, func.name, node.lineno))
    return found


def test_invoices_are_only_loaded_through_get_live_invoice():
    offenders = [
        f"{file}:{line} in {func}()"
        for file, func, line in _raw_invoice_gets()
        if (file, func) not in ALLOWED
    ]
    assert not offenders, (
        "Load invoices with services.invoices.get_live_invoice, not "
        "db.get(Invoice, ...):\n  " + "\n  ".join(offenders)
    )


def test_the_check_finds_the_helper_itself():
    # guards the test: if the AST search ever stops matching, the test above
    # would pass vacuously
    assert ("services/invoices.py", "get_live_invoice") in {
        (file, func) for file, func, _ in _raw_invoice_gets()
    }


def test_get_live_invoice_hides_a_deleted_invoice_already_in_the_session(
    client, engine, test_user, test_project, vendor_auth_headers
):
    """The exact gap the helper exists for: the invoice is loaded in the
    session first, then deleted, then looked up again in the same session."""
    from datetime import datetime, timezone
    from uuid import UUID

    from sqlalchemy.orm import Session

    from models import Invoice
    from services.invoices import get_live_invoice

    created = client.post("/invoices", json={
        "totalAmount": 100.0,
        "depositPercentage": 100,
        "invoiceAssignedTo": test_user["userId"],
        "projectAssociatedTo": test_project["projectId"],
    }, headers=vendor_auth_headers).json()
    invoice_id = UUID(created["invoiceId"])

    with Session(engine) as db:
        invoice = db.get(Invoice, invoice_id)  # now in this session's identity map
        invoice.invoiceDeletedAt = datetime.now(timezone.utc)
        db.flush()

        # a raw db.get still hands back the deleted invoice...
        assert db.get(Invoice, invoice_id) is invoice
        # ...the helper doesn't
        assert get_live_invoice(db, invoice_id) is None
        db.rollback()
