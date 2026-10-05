import os
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL")
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
