"""Pydantic schemas package.

Folder intent:
  common.py             — CamelModel base + HealthResponse (all schemas inherit CamelModel)
  coi_verification.py   — COI verification & AI extraction response schemas (used by /api/coi/* routes)
  vendor.py             — REFERENCE pattern (copy when adding Building, Agent, etc.)
"""
