from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base. Alembic autogenerate reads metadata from here.

    Every model module must be imported in app/models/__init__.py, otherwise
    autogenerate will not see the table and will emit a drop.
    """
