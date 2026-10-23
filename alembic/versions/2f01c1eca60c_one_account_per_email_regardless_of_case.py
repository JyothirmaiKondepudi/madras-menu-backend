"""one account per email regardless of case

Emails are now stored lowercase by the API. This lowercases existing rows and
adds a unique index on lower(email), so Jane@x.com and jane@x.com can't be
two accounts. Stops with a clear error, changing nothing, if two existing
accounts already differ only in case: those have to be merged by hand first.

Revision ID: 2f01c1eca60c
Revises: f17b51cc1276
Create Date: 2026-10-17 17:39:30.024649

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f01c1eca60c'
down_revision: Union[str, Sequence[str], None] = 'f17b51cc1276'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    clashes = op.get_bind().execute(sa.text(
        "SELECT lower(email) FROM user_data GROUP BY lower(email) HAVING count(*) > 1"
    )).scalars().all()
    if clashes:
        raise RuntimeError(
            "These emails belong to more than one account, differing only in "
            f"capitalization; merge them before migrating: {', '.join(clashes)}"
        )
    op.execute("UPDATE user_data SET email = lower(email) WHERE email <> lower(email)")
    op.create_index(
        "user_data_email_lower_key", "user_data", [sa.text("lower(email)")], unique=True
    )


def downgrade() -> None:
    # emails stay lowercase: the original capitalization isn't kept anywhere
    op.drop_index("user_data_email_lower_key", table_name="user_data")
