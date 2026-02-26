"""Vendor repository — REFERENCE pattern for all repositories.

How to add a new repository:
  1. Create app/repositories/my_entity.py
  2. class MyEntityRepository(BaseRepository[MyEntity]):
         model = MyEntity
  3. Add any domain-specific query methods as needed
"""


from app.domain.vendor import Vendor
from app.repositories.base import BaseRepository


class VendorRepository(BaseRepository[Vendor]):
    model = Vendor
    # Add custom query methods here as features grow.
    # e.g. search by company name, filter by status, etc.
