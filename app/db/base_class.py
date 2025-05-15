# app/db/base_class.py
from sqlalchemy.ext.declarative import as_declarative, declared_attr
from typing import Any # For type hinting id

@as_declarative()
class Base:
    """
    Base class for SQLAlchemy models.
    It includes a default __tablename__ generator.
    """
    id: Any  # Provides a default type hint for 'id' common in models
    __name__: str

    # Generate __tablename__ automatically from class name
    # e.g., UserProfile -> user_profiles
    @declared_attr
    def __tablename__(cls) -> str:
        import re
        # Convert CamelCase to snake_case and add 's' for plural
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', cls.__name__)
        name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        if not name.endswith('s'): # simple pluralization
             name += 's'
        return name

