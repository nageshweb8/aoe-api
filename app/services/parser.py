"""
ACORD 25 Certificate of Liability Insurance — PDF layout-aware parser.

Uses **pdfplumber** for column-aware table extraction.
ACORD 25 forms are structured, column-based, fixed-layout PDFs (not scanned).

Supported layouts
-----------------
* **3-table** — separate header, policy-grid, and footer tables.
* **Mega-table** — a single table containing header, policies, and footer
  (some ACORD generators merge everything into one grid).

Column positions are detected dynamically from the header row so the parser
is resilient to different ACORD 25 generators / column counts.
"""


import io
import logging
import re
from datetime import datetime

import pdfplumber

logger = logging.getLogger(__name__)

__all__ = ["parse_acord25_pdf", "extract_raw_text"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(val: str | None) -> str:
    """Strip and collapse whitespace; return empty string for None."""
    if not val:
        return ""
    return re.sub(r"\s+", " ", val).strip()

def _parse_date(raw: str) -> str | None:
    """Normalize a date string to ISO 8601 (YYYY-MM-DD).

    Accepts ``MM/DD/YYYY``, ``M/D/YYYY``, ``YYYY-MM-DD``, and ``MM-DD-YYYY``.
    """
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    # Fallback for single-digit month/day (e.g. 7/1/2024)
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(1)), int(m.group(2))).date().isoformat()
        except ValueError:
            pass
    return None

_DATE_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")

# ---------------------------------------------------------------------------
# Table 0 — Header: Producer, Insured, Insurers
# ---------------------------------------------------------------------------

def _parse_header_table(table: list[list[str | None]]) -> dict:
    """Parse the header table for producer, insured, and insurers.

    Handles two layouts:
    - **Compact**: PRODUCER/INSURED info in a single multi-line cell.
    - **Mega-table**: PRODUCER/INSURED as standalone labels with data in
      subsequent rows / adjacent columns.
    """
    result: dict = {
        "producer": {"name": "", "address": None, "phone": None, "fax": None, "email": None},
        "insured": {"name": "", "address": None},
        "insurers": [],
        "certificateDate": None,
    }

    # ---- Flatten all cells once for searches & per-row scanning ----
    # Track row indices where PRODUCER / INSURED labels appear
    producer_row_idx: int | None = None
    insured_row_idx: int | None = None

    for ri, row in enumerate(table):
        for ci, cell in enumerate(row):
            if not cell:
                continue
            text = cell.strip()

            # Certificate date (may be in a dedicated cell or same cell as label)
            if "DATE (MM/DD/YYYY)" in text:
                dates = _DATE_RE.findall(text)
                if dates:
                    result["certificateDate"] = _parse_date(dates[0])
                else:
                    # Date might be in the next row, same column
                    for nri in range(ri + 1, min(ri + 3, len(table))):
                        for nc in table[nri]:
                            if nc:
                                d = _DATE_RE.findall(nc.strip())
                                if d:
                                    result["certificateDate"] = _parse_date(d[0])
                                    break
                        if result["certificateDate"]:
                            break

            # ---- Producer block (compact: "PRODUCER\nName\nAddr") ----
            if text.startswith("PRODUCER\n"):
                lines = [ln.strip() for ln in text.split("\n")
                         if ln.strip() and ln.strip() != "PRODUCER"]
                if lines:
                    result["producer"]["name"] = lines[0]
                    if len(lines) > 1:
                        result["producer"]["address"] = ", ".join(lines[1:])

            # Standalone "PRODUCER" label (mega-table)
            if text == "PRODUCER":
                producer_row_idx = ri

            # ---- Insured block (compact) ----
            if text.startswith("INSURED\n"):
                lines = [ln.strip() for ln in text.split("\n")
                         if ln.strip() and ln.strip() != "INSURED"]
                if lines:
                    result["insured"]["name"] = lines[0]
                    if len(lines) > 1:
                        result["insured"]["address"] = ", ".join(lines[1:])

            # Standalone "INSURED" label (mega-table)
            if text == "INSURED":
                insured_row_idx = ri

            # Phone
            if "PHONE" in text.upper() and ("Ext)" in text or "(A/C" in text):
                m = re.search(r"([\d\-\(\)]{7,})", text)
                if m:
                    result["producer"]["phone"] = m.group(1).strip()

            # Fax
            if "FAX" in text.upper() and ("No)" in text or "(A/C" in text):
                m = re.search(r"No\)?[:\s]*([\d\-\(\)]{7,})", text)
                if m:
                    result["producer"]["fax"] = m.group(1).strip()

            # Email
            if "E-MAIL" in text.upper() or "@" in text:
                m = re.search(r"([\w.\-+]+@[\w.\-]+\.\w+)", text)
                if m:
                    result["producer"]["email"] = m.group(1)

            # ---- Insurer lines ----
            # Format 1: "INSURER A : CompanyName" (within one cell)
            # Format 2: "INSURER A :" in one cell, name in another cell on the same row
            insurer_matches = list(re.finditer(
                r"INSURER\s+([A-F])\s*:\s*(.*?)(?=\n|$)", text, re.IGNORECASE
            ))
            for im in insurer_matches:
                letter = im.group(1).upper()
                name = _clean(im.group(2))

                # If name is empty, look for it elsewhere:
                if not name:
                    # 1) Text before "INSURER X :" in the same cell
                    pre_text = text[:im.start()].strip()
                    pre_lines = [
                        ln.strip() for ln in pre_text.split("\n")
                        if ln.strip()
                        and not ln.strip().startswith("INSURER")
                        and not re.match(r"^(NAIC|INSURER\(S\))", ln.strip(), re.IGNORECASE)
                    ]
                    if pre_lines:
                        name = pre_lines[-1]

                    # 2) Check neighboring cells in the same row
                    if not name:
                        for oci in range(ci + 1, len(row)):
                            oc = row[oci]
                            if oc and len(oc.strip()) > 3:
                                candidate = oc.strip()
                                # Skip NAIC numbers and other insurer labels
                                if (
                                    not re.match(r"^\d+$", candidate)
                                    and "INSURER" not in candidate.upper()
                                    and "NAIC" not in candidate.upper()
                                ):
                                    name = candidate
                                    break

                if name and len(name) > 2:
                    naic = None
                    for other_cell in row:
                        if other_cell and re.match(r"^\d{4,6}$", other_cell.strip()):
                            naic = other_cell.strip()
                    if not any(ins["letter"] == letter for ins in result["insurers"]):
                        result["insurers"].append({
                            "letter": letter,
                            "name": name,
                            "naicNumber": naic,
                        })

    # ---- Handle standalone PRODUCER label (mega-table format) ----
    if producer_row_idx is not None and not result["producer"]["name"]:
        addr_parts: list[str] = []
        for ri in range(producer_row_idx + 1, min(producer_row_idx + 6, len(table))):
            row = table[ri]
            cell0 = _clean(row[0]) if row[0] else ""
            if not cell0:
                continue
            # Stop at INSURED or INSURER labels
            if cell0.upper() in ("INSURED",) or cell0.upper().startswith("INSURER"):
                break
            addr_parts.append(cell0)
        if addr_parts:
            result["producer"]["name"] = addr_parts[0]
            if len(addr_parts) > 1:
                result["producer"]["address"] = ", ".join(addr_parts[1:])

    # ---- Handle standalone INSURED label (mega-table format) ----
    if insured_row_idx is not None and not result["insured"]["name"]:
        addr_parts = []
        for ri in range(insured_row_idx + 1, min(insured_row_idx + 6, len(table))):
            row = table[ri]
            cell0 = _clean(row[0]) if row[0] else ""
            if not cell0:
                continue
            if cell0.upper().startswith("COVERAGES") or cell0.upper().startswith("THIS IS TO CERTIFY"):
                break
            addr_parts.append(cell0)
        if addr_parts:
            result["insured"]["name"] = addr_parts[0]
            if len(addr_parts) > 1:
                result["insured"]["address"] = ", ".join(addr_parts[1:])

    return result

# ---------------------------------------------------------------------------
# Table 2 — Footer: Certificate Holder
# ---------------------------------------------------------------------------

def _parse_footer_table(table: list[list[str | None]]) -> dict | None:
    """Parse the footer table for certificate holder."""
    for row in table:
        for cell in row:
            if not cell:
                continue
            text = cell.strip()
            # Skip cancellation boilerplate and form labels
            upper = text.upper()
            if any(kw in upper for kw in ("SHOULD", "AUTHORIZED", "CANCELLATION",
                                          "CERTIFICATE HOLDER", "ACORD 25", "©")):
                continue
            # Skip very short fragments (like split cells: "QS", "press, TX")
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            if not lines:
                continue
            # Need at least a reasonable name (>3 chars, starts with uppercase)
            if len(lines[0]) < 4:
                continue
            # Skip fragments (should start with uppercase letter or digit)
            if not re.match(r"^[A-Z0-9]", lines[0]):
                continue
            return {
                "name": lines[0],
                "address": ", ".join(lines[1:]) if len(lines) > 1 else None,
            }
    return None

# ---------------------------------------------------------------------------
# Table 1 — Policy grid
# ---------------------------------------------------------------------------

# Known insurance type keywords
_INSURANCE_KEYWORDS = {
    "COMMERCIAL GENERAL LIABILITY",
    "AUTOMOBILE LIABILITY",
    "UMBRELLA LIAB",
    "EXCESS LIAB",
    "WORKERS COMPENSATION",
    "WORKERS' COMPENSATION",
    "EMPLOYERS' LIABILITY",
    "ERRORS & OMISSIONS",
    "ERRORS & OMMISIONS",
    "ERRORS AND OMISSIONS",
    "PROFESSIONAL LIABILITY",
    "CYBER LIABILITY",
    "3RD PARTY CRIME",
    "THIRD PARTY CRIME",
    "CRIME",
}

def _is_insurance_type(text: str) -> bool:
    upper = text.upper()
    return any(kw in upper for kw in _INSURANCE_KEYWORDS)

def _normalize_type(raw: str) -> str:
    """Clean insurance type to a display-friendly name."""
    # Take only the first line (main type), strip checkbox artifacts
    main_line = raw.split("\n")[0].strip()
    main_line = re.sub(r"^[X✓☐☑]\s*", "", main_line).strip()
    # Remove trailing sub-type noise
    main_line = re.sub(r"\s*(CLAIMS-MADE|OCCUR).*$", "", main_line, flags=re.IGNORECASE).strip()

    # Title case
    name = main_line.title()
    # Fix casing
    name = name.replace(" And ", " & ").replace("Liab ", "Liability ")
    name = name.replace("Ommisions", "Omissions").replace("3Rd", "3rd")
    name = name.replace("Liability Liability", "Liability")
    # Normalize combined WC/EL type to just Workers Compensation
    if "Workers Compensation" in name and "Employers" in name:
        name = "Workers Compensation"
    return name.strip()

def _find_column_indices(header_row: list[str | None]) -> dict[str, int] | None:
    """Dynamically find column indices from the header row labels."""
    cols: dict[str, int] = {}
    for i, cell in enumerate(header_row):
        if not cell:
            continue
        upper = cell.upper()
        if "POLICY NUMBER" in upper:
            cols["pn"] = i
        elif "POLICY EFF" in upper:
            cols["eff"] = i
        elif "POLICY EXP" in upper:
            cols["exp"] = i
        elif "LIMITS" in upper:
            cols.setdefault("limits", i)  # first LIMITS column
        elif "INSR" in upper and "LTR" in upper:
            cols["ltr"] = i
    if "pn" not in cols:
        return None
    # Defaults: if eff/exp not found, assume adjacent to pn
    cols.setdefault("eff", cols["pn"] + 1)
    cols.setdefault("exp", cols["pn"] + 2)
    cols.setdefault("limits", cols["exp"] + 1)
    cols.setdefault("ltr", 0)
    return cols

def _collect_limits_range(
    row: list[str | None], limits_start: int
) -> dict[str, str]:
    """Collect limit name→value pairs from the limits region of a row.

    Scans from ``limits_start`` to the end of the row.  Limit *names* appear
    in the first cell of the region and the corresponding *values* appear in
    one of the trailing cells.
    """
    limits: dict[str, str] = {}
    if limits_start >= len(row):
        return limits

    # Collect all non-empty cells in the limits region
    name_cell = ""
    value_cell = ""
    for ci in range(limits_start, len(row)):
        txt = _clean(row[ci]) if row[ci] else ""
        if not txt or txt == "$":
            continue
        # If it looks like a dollar amount => value, else => name
        if re.search(r"\d", txt) and ("$" in txt or re.match(r"^[\d,.\s$]+$", txt)):
            value_cell = txt
        else:
            name_cell = txt

    if name_cell and value_cell:
        value = value_cell.strip()
        value = re.sub(r"\s*\$\s*$", "", value)
        value = re.sub(r"^\$\s*", "", value)
        if value:
            limits[name_cell] = "$" + value

    return limits

# Limits-based insurance type inference (when type text is missing/partial)
_LIMITS_TYPE_MAP = [
    ({"GENERAL AGGREGATE", "PRODUCTS", "PERSONAL"}, "Commercial General Liability"),
    ({"COMBINED SINGLE LIMIT"}, "Automobile Liability"),
    ({"PER STATUTE", "E.L. EACH ACCIDENT", "E.L.EACHACCIDENT", "STATUTE"}, "Workers Compensation"),
    ({"AGGREGATE"}, "Umbrella/Excess Liability"),
]

def _infer_type_from_limits(all_limit_names: set[str]) -> str:
    """Infer the insurance type from accumulated limit names."""
    upper_names = " ".join(all_limit_names).upper()
    for keywords, type_name in _LIMITS_TYPE_MAP:
        if any(kw.upper() in upper_names for kw in keywords):
            return type_name
    return "Other"

def _parse_policy_table(table: list[list[str | None]]) -> list[dict]:
    """
    Parse the ACORD 25 policy table with dynamic column detection and
    stateful row scanning.

    Handles:
    - Variable column layouts (different ACORD 25 generators use different
      column counts / positions)
    - Multi-line cells (multiple policies encoded as newline-separated values)
    - Limits in continuation rows (no policy number, only limits data)
    - Insurance type text split across columns or missing entirely
    """
    policies: list[dict] = []
    seen: set[str] = set()

    if len(table) < 3:
        return policies

    # ---- Find header row & column indices ----
    header_idx = None
    cols: dict[str, int] | None = None
    for i, row in enumerate(table):
        cols = _find_column_indices(row)
        if cols is not None:
            header_idx = i
            break

    if header_idx is None or cols is None:
        return policies

    pn_col = cols["pn"]
    eff_col = cols["eff"]
    exp_col = cols["exp"]
    limits_col = cols["limits"]
    ltr_col = cols["ltr"]

    # ---- Helper closures ----

    def _cell(row: list, col: int) -> str:
        if col < len(row) and row[col]:
            return row[col].strip()
        return ""

    def _split_cell(row: list, col: int) -> list[str]:
        raw = _cell(row, col)
        if not raw:
            return [""]
        return [ln.strip() for ln in raw.split("\n") if ln.strip()]

    def _find_type_in_row(row: list) -> str:
        """Scan type columns (between ltr and pn) for insurance type text."""
        for ci in range(max(ltr_col + 1, 1), pn_col):
            txt = _cell(row, ci)
            if txt and _is_insurance_type(txt):
                return txt
        # Also try concatenating all type-region cells for partial matches
        concat = " ".join(_cell(row, ci) for ci in range(max(ltr_col + 1, 1), pn_col))
        if _is_insurance_type(concat):
            return concat
        return ""

    # ---- Stateful scan ----
    # type_queue holds insurance type names to be consumed by upcoming policies.
    # When a multi-line type cell is found (e.g. "E&O\n3rd Party Crime"), both
    # lines are queued.  Single-row policies consume one type per entry; the
    # remaining types carry over to subsequent rows.
    type_queue: list[str] = []
    current_letter = ""
    last_consumed_type = ""   # Fallback when queue is empty (same section)
    last_policy_idx: int | None = None
    # Accumulate limit names for type inference when type text is missing
    pending_limit_names: set[str] = set()

    def _extract_type_names(raw: str) -> list[str]:
        """Split raw type cell text into individual insurance type names,
        filtering out checkbox / sub-option noise."""
        names: list[str] = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Strip trailing Y/N indicators
            line = re.sub(r"\s+Y\s*/\s*N\s*$", "", line).strip()
            # Skip checkbox / sub-option noise
            if re.match(
                r"^(X|Y|N|N/A|DED|RETENTION|CLAIMS-MADE|OCCUR|POLICY|PRO-|JECT"
                r"|LOC|GEN.L|ANY AUTO|OWNED|HIRED|SCHEDULED|NON-OWNED|If\b)"
                r"|^[X✓☐☑\s]+$"
                r"|^\$",
                line,
                re.IGNORECASE,
            ):
                continue
            # Must contain letters (not just dollar amounts or numbers)
            if not re.search(r"[A-Za-z]{3,}", line):
                continue
            # Continuation line (e.g. "AND EMPLOYERS' LIABILITY") — merge
            if line.upper().startswith("AND ") and names:
                names[-1] = names[-1] + " " + line
                continue
            names.append(line)
        return names

    for row in table[header_idx + 1:]:
        if not row:
            continue

        # Detect insurance type in this row
        row_type = _find_type_in_row(row)
        if row_type:
            type_names = _extract_type_names(row_type)
            if type_names:
                type_queue = type_names  # replace queue with new types

        # Detect insurer letter in this row
        row_letter = _cell(row, ltr_col)
        if row_letter and re.match(r"^[A-F](\n[A-F])*$", row_letter):
            current_letter = row_letter

        # Get policy data
        pn_raw = _cell(row, pn_col)
        eff_raw = _cell(row, eff_col)
        exp_raw = _cell(row, exp_col)

        # Collect limits from this row
        row_limits = _collect_limits_range(row, limits_col)

        # ---- Continuation row: limits only ----
        if not pn_raw and row_limits and last_policy_idx is not None:
            existing_limits = policies[last_policy_idx].get("limits") or {}
            existing_limits.update(row_limits)
            policies[last_policy_idx]["limits"] = existing_limits
            pending_limit_names.update(row_limits.keys())

            # If the last policy has type "Other", try to infer from accumulated limits
            if policies[last_policy_idx]["typeOfInsurance"] == "Other":
                inferred = _infer_type_from_limits(pending_limit_names)
                if inferred != "Other":
                    old_key = f"Other|{policies[last_policy_idx]['policyNumber']}"
                    seen.discard(old_key)
                    policies[last_policy_idx]["typeOfInsurance"] = inferred
                    new_key = f"{inferred}|{policies[last_policy_idx]['policyNumber']}"
                    seen.add(new_key)
            continue

        # ---- Row without policy number or dates: update state only ----
        if not pn_raw or not eff_raw or not exp_raw:
            if row_limits:
                pending_limit_names.update(row_limits.keys())
            continue

        # ---- Row with policy data: create policy entries ----
        pn_lines = _split_cell(row, pn_col)
        eff_lines = _split_cell(row, eff_col)
        exp_lines = _split_cell(row, exp_col)
        ltr_lines = _split_cell(row, ltr_col)

        # Limits may also be multi-line
        limits_names = _split_cell(row, limits_col) if limits_col < len(row) else [""]
        limits_vals_col = len(row) - 1
        limits_vals = _split_cell(row, limits_vals_col) if row[-1] else [""]

        num_entries = max(len(pn_lines), 1)

        for idx in range(num_entries):
            policy_number = _clean(pn_lines[idx]) if idx < len(pn_lines) else ""
            eff_date_str = _clean(eff_lines[idx]) if idx < len(eff_lines) else ""
            exp_date_str = _clean(exp_lines[idx]) if idx < len(exp_lines) else ""
            insurer_letter = _clean(ltr_lines[idx]) if idx < len(ltr_lines) else current_letter

            if not policy_number:
                continue

            eff_date = _parse_date(eff_date_str)
            exp_date = _parse_date(exp_date_str)
            if not eff_date or not exp_date:
                continue

            # Consume the next type from the queue; fall back to last used type
            if type_queue:
                ins_type = type_queue.pop(0)
                last_consumed_type = ins_type
            else:
                ins_type = last_consumed_type
            type_display = _normalize_type(ins_type) if ins_type else "Other"

            # Validate insurer letter — fall back to last tracked letter
            if not insurer_letter or not re.match(r"^[A-F]$", insurer_letter):
                insurer_letter = current_letter if re.match(r"^[A-F]$", current_letter) else ""

            # Build per-entry limits
            entry_limits: dict[str, str] = {}
            lim_name = _clean(limits_names[idx]) if idx < len(limits_names) else ""
            lim_val = _clean(limits_vals[idx]) if idx < len(limits_vals) else ""
            if lim_name and lim_val and lim_val != "$":
                lim_val = re.sub(r"\s*\$\s*$", "", lim_val)
                lim_val = re.sub(r"^\$\s*", "", lim_val)
                if lim_val:
                    entry_limits[lim_name] = "$" + lim_val

            key = f"{type_display}|{policy_number}"
            if key in seen:
                continue
            seen.add(key)

            policies.append({
                "typeOfInsurance": type_display,
                "policyNumber": policy_number,
                "policyEffectiveDate": eff_date,
                "policyExpirationDate": exp_date,
                "limits": entry_limits if entry_limits else None,
                "insurerLetter": insurer_letter if insurer_letter else None,
            })
            last_policy_idx = len(policies) - 1
            pending_limit_names = set(entry_limits.keys()) if entry_limits else set()

    return policies

# ---------------------------------------------------------------------------
# Main parse function
# ---------------------------------------------------------------------------

def _has_policy_header(table: list[list[str | None]]) -> bool:
    """Check if a table contains a POLICY NUMBER header row."""
    for row in table:
        for cell in row:
            if cell and "POLICY NUMBER" in cell.upper():
                return True
    return False

def parse_acord25_pdf(pdf_bytes: bytes) -> dict:
    """
    Parse an ACORD 25 Certificate of Liability Insurance PDF.

    Uses pdfplumber for layout-aware table extraction.  Supports two common
    table layouts:
    - **3-table layout**: separate header, policy, and footer tables.
    - **Mega-table layout**: a single table containing header, policies, and
      footer together (some ACORD 25 generators produce this).

    Returns a dict matching the COIVerificationResponse schema (camelCase keys).
    """
    pdf_file = io.BytesIO(pdf_bytes)

    table_settings = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 5,
        "join_tolerance": 5,
        "edge_min_length": 10,
    }

    with pdfplumber.open(pdf_file) as pdf:
        if not pdf.pages:
            logger.warning("PDF has no pages")
            return {
                "producer": None,
                "insured": {"name": "Unknown", "address": None},
                "certificateHolder": None,
                "insurers": None,
                "certificateDate": None,
                "policies": [],
            }

        page = pdf.pages[0]
        tables = page.extract_tables(table_settings=table_settings)
        logger.info("Extracted %d table(s) from page 1", len(tables))

        header_data: dict = {}
        policies: list[dict] = []
        certificate_holder: dict | None = None

        if len(tables) >= 3 and not _has_policy_header(tables[0]):
            # ---- 3-table layout (header, policies, footer) ----
            logger.info("Detected 3-table layout")
            header_data = _parse_header_table(tables[0])
            policies = _parse_policy_table(tables[1])
            certificate_holder = _parse_footer_table(tables[2])
        else:
            # ---- Mega-table or other layout ----
            logger.info("Detected mega-table / other layout")
            # Find the table(s) containing policy data and parse all tables
            # for header info.
            for t in tables:
                if _has_policy_header(t):
                    # This table contains the policy grid (and possibly header info)
                    hd = _parse_header_table(t)
                    if not header_data.get("producer", {}).get("name"):
                        header_data = hd
                    elif hd.get("producer", {}).get("name"):
                        # Merge insurers if found in the same table
                        existing_insurers = header_data.get("insurers", [])
                        new_insurers = hd.get("insurers", [])
                        seen_letters = {i["letter"] for i in existing_insurers}
                        for ins in new_insurers:
                            if ins["letter"] not in seen_letters:
                                existing_insurers.append(ins)
                        header_data["insurers"] = existing_insurers

                    policies = _parse_policy_table(t)
                else:
                    # Try extracting header or footer from non-policy tables
                    if not header_data.get("producer", {}).get("name"):
                        hd = _parse_header_table(t)
                        if hd.get("producer", {}).get("name"):
                            header_data = hd
                    if not certificate_holder:
                        certificate_holder = _parse_footer_table(t)

    producer = header_data.get("producer")
    insured = header_data.get("insured", {"name": "Unknown", "address": None})
    insurers = header_data.get("insurers", [])
    certificate_date = header_data.get("certificateDate")

    logger.info(
        "Parsed %d policies, producer=%s, insured=%s, insurers=%d",
        len(policies),
        producer.get("name") if producer else None,
        insured.get("name"),
        len(insurers),
    )

    return {
        "producer": producer if producer and producer.get("name") else None,
        "insured": insured,
        "certificateHolder": certificate_holder,
        "insurers": insurers if insurers else None,
        "certificateDate": certificate_date,
        "policies": policies,
    }

# ---------------------------------------------------------------------------
# Raw text extraction (for AI layer)
# ---------------------------------------------------------------------------

def extract_raw_text(pdf_bytes: bytes) -> str:
    """Extract the full raw text from a PDF for AI processing.

    This is intentionally separate from the structured parse — a simple text
    dump that preserves as much content as possible for the LLM to reason
    over.
    """
    pdf_file = io.BytesIO(pdf_bytes)
    pages: list[str] = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n".join(pages)
