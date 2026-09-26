"""
The single source of truth for what permissions exist — imported by the
migration that seeds them into the real database AND by the test suite's
`engine` fixture (which builds its schema via Base.metadata.create_all(),
bypassing Alembic entirely, so it needs its own seeding). Kept in one place
on purpose: hand-maintaining two copies of this list was exactly the kind
of duplicated-state drift that caused real bugs earlier in this project
(the hierarchy tree's tracking-file drift, fixed by removing the second
copy of the truth rather than trying to keep two in sync).

One row per permission actually enforced in the app today — a faithful
conversion of every existing "userRole == vendor" check into a named
permission, not new authorization rules. See auth/dependencies.py's
require_permission()/user_has_permission() and the routes/*.py files
using them.
"""

PERMISSIONS = [
    ("user:list", "List every user account"),
    ("user:view_all", "View any user's profile, not just your own"),
    ("user:create", "Create a new user account"),
    ("user:update", "Edit any user account"),
    ("user:delete", "Delete a user account"),
    ("project:view_all", "View any project, not just ones you're linked to"),
    ("project:create", "Create a new project"),
    ("project:update", "Edit any project"),
    ("project:delete", "Delete a project"),
    ("project:manage_users", "Link/unlink a user to a project"),
    ("project:set_final_invoice", "Record which invoice a client went ahead with"),
    ("subproject:view_all", "View any subproject, not just ones on your own projects"),
    ("subproject:create", "Create a new subproject"),
    ("subproject:update", "Edit any subproject"),
    ("subproject:delete", "Delete a subproject"),
    ("invoice:view_all", "View, accept, or reject any invoice, not just your own"),
    ("invoice:create", "Create a new invoice"),
    ("invoice:update", "Edit any invoice"),
    ("invoice:delete", "Delete an invoice"),
    ("tax_category:manage", "Read or write tax categories/rates"),
    ("menu_item:create", "Add a new menu item"),
    ("menu_item:update", "Edit a menu item"),
    ("menu_item:delete", "Delete a menu item"),
    ("hierarchy:manage", "Read or write the dish hierarchy (item_relationships)"),
    ("embedding:manage", "Generate or search menu item embeddings"),
]

# role -> permission names. "client" is deliberately absent — their access
# is entirely identity/resource-scoped (user_projects, invoiceAssignedTo),
# not permission-table-driven. A future "staff"/"chef" role gets its own
# entry here, no code change required anywhere else.
ROLE_PERMISSIONS = {
    "vendor": [name for name, _ in PERMISSIONS],
}
