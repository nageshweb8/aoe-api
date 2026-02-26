"""Services package — all business logic lives here, never in routers.

Files:
  parser.py          — ACORD 25 PDF layout-aware parser (used by /api/coi/verify)
  openai_service.py  — AI/OpenAI COI extraction and validation (used by /api/coi/* routes)
  vendor.py          — REFERENCE service pattern (copy when adding Building, COI v1, etc.)

Rule: routers call services, services call repositories, repositories call the DB.
      No SQLAlchemy queries in routers. No FastAPI imports in services.
"""
