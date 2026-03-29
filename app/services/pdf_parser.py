"""
PDF / text parser for CAMS statements and Form 16.
Handles both uploaded PDF files and raw pasted text.
"""
from __future__ import annotations
import re
import io
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── CAMS statement parser ─────────────────────────────────────────────────────

def parse_cams_text(raw_text: str) -> list[dict[str, Any]]:
    """
    Parse a CAMS consolidated account statement (pasted text format).
    Returns a list of holding dicts.

    CAMS text typically looks like:
        Axis Bluechip Fund - Regular Plan - Growth
        ISIN: INF846K01DP8
        Units: 1234.567  |  NAV: ₹45.23  |  Current Value: ₹55,834
        Invested: ₹42,000  |  Gain/Loss: ₹13,834 (32.94%)
    """
    holdings: list[dict[str, Any]] = []

    # Normalise whitespace
    text = raw_text.replace("\r\n", "\n").strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    i = 0
    while i < len(lines):
        line = lines[i]

        # Detect a fund name line (heuristic: contains "Fund" or "ETF" or ends with "Growth/IDCW")
        is_fund_line = (
            any(k in line for k in ["Fund", "ETF", "Plan", "Scheme"])
            and not line.startswith("ISIN")
            and not line.startswith("Units")
        )

        if is_fund_line:
            holding: dict[str, Any] = {
                "fund_name": line,
                "isin": None,
                "units": None,
                "nav": None,
                "current_value": None,
                "invested_amount": None,
                "gain_loss": None,
                "gain_pct": None,
            }

            # Scan next few lines for details
            for j in range(i + 1, min(i + 8, len(lines))):
                detail = lines[j]

                # ISIN
                m = re.search(r"ISIN[:\s]+([A-Z0-9]{12})", detail)
                if m:
                    holding["isin"] = m.group(1)

                # Units
                m = re.search(r"Units?[:\s]+([\d,]+\.?\d*)", detail, re.IGNORECASE)
                if m:
                    holding["units"] = _num(m.group(1))

                # NAV
                m = re.search(r"NAV[:\s₹]+([\d,]+\.?\d*)", detail, re.IGNORECASE)
                if m:
                    holding["nav"] = _num(m.group(1))

                # Current value
                m = re.search(
                    r"(Current\s+Value|Market\s+Value)[:\s₹]+([\d,]+\.?\d*)",
                    detail, re.IGNORECASE
                )
                if m:
                    holding["current_value"] = _num(m.group(2))

                # Invested amount
                m = re.search(
                    r"(Invested|Cost)[:\s₹]+([\d,]+\.?\d*)",
                    detail, re.IGNORECASE
                )
                if m:
                    holding["invested_amount"] = _num(m.group(2))

                # Gain / loss percentage
                m = re.search(r"\(([+-]?\d+\.?\d*)%\)", detail)
                if m:
                    holding["gain_pct"] = float(m.group(1))

            holdings.append(holding)

        i += 1

    return holdings


def parse_cams_pdf(pdf_bytes: bytes) -> tuple[str, list[dict[str, Any]]]:
    """
    Extract text from a CAMS PDF and parse holdings.
    Returns (raw_text, holdings_list).
    """
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber not installed. Run: pip install pdfplumber")

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages_text = []
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages_text.append(text)
        raw_text = "\n".join(pages_text)

    holdings = parse_cams_text(raw_text)
    return raw_text, holdings


# ── Form 16 / salary slip parser ──────────────────────────────────────────────

def parse_form16(text: str) -> dict[str, float]:
    """
    Extract key numbers from a Form 16 or salary structure (pasted text).
    Returns a dict of financial fields.
    """
    result: dict[str, float] = {}

    patterns = {
        "gross_salary": r"Gross\s+Salary[:\s₹]+([\d,]+)",
        "basic_salary": r"Basic\s+(?:Salary)?[:\s₹]+([\d,]+)",
        "hra_received": r"HRA\s+(?:Received|paid)?[:\s₹]+([\d,]+)",
        "special_allowance": r"Special\s+Allowance[:\s₹]+([\d,]+)",
        "pf_deduction": r"(?:PF|Provident\s+Fund)[:\s₹]+([\d,]+)",
        "tds_deducted": r"TDS\s+(?:deducted)?[:\s₹]+([\d,]+)",
        "standard_deduction": r"Standard\s+Deduction[:\s₹]+([\d,]+)",
        "income_tax": r"Income\s+Tax[:\s₹]+([\d,]+)",
    }

    for field, pattern in patterns.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            result[field] = _num(m.group(1))

    return result


# ── Helpers ────────────────────────────────────────────────────────────────────

def _num(s: str) -> float:
    """Remove commas/₹ and parse as float."""
    try:
        return float(s.replace(",", "").replace("₹", "").strip())
    except ValueError:
        return 0.0


def summarise_holdings(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate metrics from parsed holdings list."""
    total_invested = sum(h.get("invested_amount") or 0 for h in holdings)
    total_current = sum(h.get("current_value") or 0 for h in holdings)
    total_gain = total_current - total_invested
    gain_pct = (total_gain / total_invested * 100) if total_invested else 0

    return {
        "fund_count": len(holdings),
        "total_invested": round(total_invested),
        "total_current_value": round(total_current),
        "absolute_gain": round(total_gain),
        "gain_pct": round(gain_pct, 2),
    }
