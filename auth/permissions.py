"""Single source of truth for permissions — used by the seed migration and the test suite's engine fixture."""

PERMISSIONS = [
    ("user:list", "List every user account"),
    ("user:view_all", "View any user's profile, not just your own"),
    ("user:create", "Create a new user account"),
    ("user:update", "Edit any user account"),
    ("user:disable", "Disable or re-enable a user account"),
    ("user:delete", "Delete a user account"),
    ("user:grant_platform_admin", "Create users with the platform_admin role"),
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
    (
        "billing:view_all",
        "View any subproject's billing history/info, not just your own",
    ),
    (
        "billing:create",
        "Record a billing transaction (e.g. a manually-entered payment)",
    ),
    ("tax_category:manage", "Read or write tax categories/rates"),
    ("menu_item:create", "Add a new menu item"),
    ("menu_item:update", "Edit a menu item"),
    ("menu_item:delete", "Delete a menu item"),
    ("hierarchy:manage", "Read or write the dish hierarchy (item_relationships)"),
    ("embedding:manage", "Generate or search menu item embeddings"),
    ("org:list", "list every org present"),
    ("org:view_all", "view any org profile"),
    ("org:create", "create a new org"),
    ("org:update", "edit org account"),
    ("org:delete", "delete org account"),
]

# role -> permission names. "client" is absent — its access is resource-scoped, not permission-based.
#
# "org:view_all" is deliberately excluded from vendor's blanket grant — a
# vendor is meant to see their own organization via identity (User.userOrg),
# not a blanket "view any org" permission. Granting it to the whole role
# meant any vendor could view (and, via the same check reused there, update)
# every OTHER org too — a real cross-tenant leak, caught by testing live
# rather than assumed away. Reserved for a future platform-operator/sales
# role once that actually exists — see routes/organizations.py.
_VENDOR_EXCLUDED_PERMISSIONS = {
    "org:view_all",
    "user:grant_platform_admin",
    "org:create",
    "org:delete",
    "org:list",
}
ROLE_PERMISSIONS = {
    "vendor": [
        name for name, _ in PERMISSIONS if name not in _VENDOR_EXCLUDED_PERMISSIONS
    ],
    "platform_admin": [name for name, _ in PERMISSIONS],
}
