from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session, with_loader_criteria
from sqlalchemy import event

from config import database_url

DATABASE_URL = database_url()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Foreign keys without an explicit name= get the same name Postgres would
# give them (<table>_<column>_fkey), so migrations can drop and recreate them.
# "ix" is SQLAlchemy's default for index=True; it has to be repeated here
# because passing naming_convention replaces the defaults.
Base = declarative_base(
    metadata=MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "fk": "%(table_name)s_%(column_0_name)s_fkey",
        }
    )
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@event.listens_for(Session, "do_orm_execute")
def _hide_deleted_invoices(state):
    if state.is_select and not state.execution_options.get("include_deleted", False):
        from models import Invoice  # imported here: models imports database

        state.statement = state.statement.options(
            with_loader_criteria(
                Invoice,
                lambda cls: cls.invoiceDeletedAt.is_(None),
                include_aliases=True,
            )
        )
