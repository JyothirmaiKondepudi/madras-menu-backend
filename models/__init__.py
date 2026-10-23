"""
Split out of a single model.py, one file per entity — matching how
routes/ and services/ are already organized. Re-exports every class here
so existing call sites only need `model` -> `models` in their import line
(e.g. `from model import User` -> `from models import User`), not a
rewrite of every import statement across the app.

Importing every submodule here also registers every class on Base.metadata
as a side effect — required for Alembic autogenerate and for the test
suite's `Base.metadata.create_all()` to see the full schema, exactly like
`import model` used to.
"""

from .user import User
from .project import Project, user_projects
from .invoice import Invoice
from .invoice_document import InvoiceLineItem, InvoiceNumberCounter
from .subproject import Subproject
from .tax_category import TaxCategory
from .menu_item import MenuItem
from .item_relationship import ItemRelationship
from .permission import Permission, RolePermission
from .notifications import Notification
from .billing_history import BillingHistory
from .billing_info import BillingInfo
from .account_activity import AccountActivity
from .organizations import Organization
from .catalog import Equipment, RateCardItem
from .live_station import LiveStation
from .api_logs import ApiLogs

__all__ = [
    "User",
    "Project",
    "user_projects",
    "Invoice",
    "InvoiceLineItem",
    "InvoiceNumberCounter",
    "Subproject",
    "TaxCategory",
    "MenuItem",
    "ItemRelationship",
    "Permission",
    "RolePermission",
    "Notification",
    "BillingHistory",
    "BillingInfo",
    "AccountActivity",
    "Organization",
    "RateCardItem",
    "Equipment",
    "LiveStation",
    "ApiLogs",
]
