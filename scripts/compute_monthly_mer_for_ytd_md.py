#!/usr/bin/env python3
import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MD_PATH = ROOT / "data" / "reports" / "executive" / "ytd-statistics-2025-09-15.md"

# Data sources
NB_2025_CSV = ROOT / "data" / "ads" / "ytd_sales_data-higher_dose_llc-2025_09_27_05_46_35.csv"
SHOPIFY_2025_OU = ROOT / "data" / "ads" / "q4-planning-2025" / "shopify" / "Total sales over time - OU - 2025-01-01 - 2025-09-16.csv"
SHOPIFY_2024_FULL = ROOT / "data" / "ads" / "q4-planning-2025" / "shopify" / "Total sales over time - 01-01-2024-12-31-2024.csv"
HISTORICAL_SPEND_2024 = ROOT / "data" / "ads" / "q4-planning-2025" / "Historical Spend - Historical Spend.csv"


def _coerce_currency(val: str | float | int) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val)
    s = s.replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except Exception:
        return 0.0


def parse_historical_total_spend(csv_path: Path) -> pd.DataFrame:
    rows: list[dict[str, str | float]] = []
    if not csv_path.exists():
        return pd.DataFrame(columns=["month", "total_spend"])  # empty
    with csv_path.open("r", newline="") as f:
        reader = csv.reader(f)
        for parts in reader:
            if not parts:
                continue
            first = parts[0].strip() if parts else ""
            # Month rows look like 'Oct-24' etc
            if len(first) >= 6 and first[3] == "-":
                # convert like 'Oct-24' to YYYY-MM using datetime strptime fallback
                mon = None
                try:
                    dt = datetime.strptime(first, "%b-%y")
                    mon = f"{dt.year:04d}-{dt.month:02d}"
                except Exception:
                    pass
                if not mon:
                    continue
                val = parts[-1] if parts else "0"
                rows.append({"month": mon, "total_spend": _coerce_currency(val)})
    return pd.DataFrame(rows)


def monthly_spend_2025_from_nb(nb_csv: Path, cutoff: datetime | None = None) -> dict[str, float]:
    df = pd.read_csv(nb_csv, low_memory=False, usecols=["date", "accounting_mode", "spend"])  # type: ignore[arg-type]
    # Normalize date
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    # Filter to 2025 and Cash snapshot when available
    mask_2025 = df["date"].dt.year == 2025
    df = df[mask_2025].copy()
    # Clip to cutoff when provided
    if cutoff is not None:
        df = df[df["date"] <= cutoff].copy()
    if "accounting_mode" in df.columns:
        am = df["accounting_mode"].astype(str).str.lower().str.strip()
        df = df[am.str.contains("cash", na=False)].copy()
    # Coerce spend numeric
    df["spend"] = pd.to_numeric(df["spend"], errors="coerce").fillna(0.0)
    df["month"] = df["date"].dt.to_period("M").astype(str)
    out = df.groupby("month")["spend"].sum().to_dict()
    return {k: float(v) for k, v in out.items()}


def monthly_revenue_2025_from_shopify(shopify_ou_csv: Path, cutoff: datetime | None = None) -> dict[str, float]:
    df = pd.read_csv(shopify_ou_csv)
    # Expect 'Day' and 'Total sales'
    if "Day" not in df.columns or "Total sales" not in df.columns:
        raise SystemExit("Shopify 2025 OU file missing required columns 'Day' and 'Total sales'")
    df = df.copy()
    df["Day"] = pd.to_datetime(df["Day"], errors="coerce")
    df = df.dropna(subset=["Day"])
    if cutoff is not None:
        df = df[df["Day"] <= cutoff].copy()
    df["month"] = df["Day"].dt.to_period("M").astype(str)
    ser = (
        pd.to_numeric(df["Total sales"], errors="coerce").fillna(0.0)
        .groupby(df["month"]).sum()
    )
    return {k: float(v) for k, v in ser.to_dict().items()}


def monthly_revenue_2024_from_shopify(shopify_2024_csv: Path) -> dict[str, float]:
    df = pd.read_csv(shopify_2024_csv)
    if "Month" not in df.columns or "Total sales" not in df.columns:
        raise SystemExit("Shopify 2024 file missing 'Month' and 'Total sales'")
    df = df.copy()
    df["_m"] = pd.to_datetime(df["Month"], errors="coerce").dt.to_period("M").astype(str)
    ser = pd.to_numeric(df["Total sales"], errors="coerce").fillna(0.0).groupby(df["_m"]).sum()
    return {k: float(v) for k, v in ser.to_dict().items()}


def monthly_prev_year_revenue_to_cutoff_from_ou(shopify_2025_ou: Path, cutoff: datetime | None) -> dict[str, float]:
    """For the cutoff month only, compute previous-year revenue through the cutoff day using the
    'Total sales (previous_year)' column in the 2025 OU file. Returns mapping like {'2024-09': value}.
    """
    out: dict[str, float] = {}
    if cutoff is None:
        return out
    try:
        df = pd.read_csv(shopify_2025_ou)
        if 'Day' not in df.columns:
            return out
        prev_col = None
        for cand in ["Total sales (previous_year)", "Total sales (previous year)", "Total sales prev year"]:
            if cand in df.columns:
                prev_col = cand
                break
        if prev_col is None:
            return out
        w = df.copy()
        w['Day'] = pd.to_datetime(w['Day'], errors='coerce')
        w = w.dropna(subset=['Day'])
        # Keep rows for the cutoff month (current year month)
        is_cut_month = (w['Day'].dt.year == cutoff.year) & (w['Day'].dt.month == cutoff.month)
        w = w[is_cut_month]
        # Clip to cutoff day
        w = w[w['Day'].dt.day <= cutoff.day]
        # Sum previous-year revenue for these days
        val = float(pd.to_numeric(w[prev_col], errors='coerce').fillna(0).sum())
        out[f"{cutoff.year-1}-{cutoff.month:02d}"] = val
        return out
    except Exception:
        return out


def read_cutoff_from_md(md_path: Path) -> datetime | None:
    try:
        txt = md_path.read_text(encoding="utf-8")
        # Look for '(through YYYY-MM-DD)'
        import re
        m = re.search(r"through\s+(\d{4}-\d{2}-\d{2})", txt)
        if m:
            return datetime.strptime(m.group(1), "%Y-%m-%d")
    except Exception:
        return None
    return None


def compute_mer_tables() -> dict[str, dict[str, float]]:
    # 2025 MER: Shopify revenue / NB spend
    cutoff = read_cutoff_from_md(MD_PATH)
    nb25 = monthly_spend_2025_from_nb(NB_2025_CSV, cutoff=cutoff)
    rev25 = monthly_revenue_2025_from_shopify(SHOPIFY_2025_OU, cutoff=cutoff)
    mer25: dict[str, float] = {}
    for m, sp in nb25.items():
        rv = float(rev25.get(m, 0.0))
        mer25[m] = (rv / sp) if sp > 0 else 0.0

    # 2024 MER: Shopify revenue / Historical Spend
    rev24 = monthly_revenue_2024_from_shopify(SHOPIFY_2024_FULL)
    # Adjust 2024 revenue for the cutoff month to be through the cutoff day
    if cutoff is not None:
        adj = monthly_prev_year_revenue_to_cutoff_from_ou(SHOPIFY_2025_OU, cutoff)
        rev24.update(adj)
    hspend = parse_historical_total_spend(HISTORICAL_SPEND_2024)
    spend24_map = {str(r["month"]): float(r["total_spend"]) for _, r in hspend.iterrows()}
    mer24: dict[str, float] = {}
    for m, rv in rev24.items():
        sp = float(spend24_map.get(m, 0.0))
        mer24[m] = (rv / sp) if sp > 0 else 0.0

    return {"mer25": mer25, "mer24": mer24, "rev25": rev25, "rev24": rev24}


def format_pct_delta(a: float, b: float) -> str:
    if b == 0:
        return "N/A"
    return f"{((a - b) / b) * 100:+.2f}%"


def usd(x: float) -> str:
    try:
        return f"${x:,.0f}"
    except Exception:
        return f"${x}"


def update_md_table(md_path: Path, mer25: dict[str, float], mer24: dict[str, float], rev25: dict[str, float], rev24: dict[str, float]) -> None:
    lines = md_path.read_text(encoding="utf-8").splitlines()

    # Find the Monthly Trends table header
    header_idx = None
    for i, ln in enumerate(lines):
        if ln.strip().startswith("| Month | 2025 Orders "):
            header_idx = i
            break
    if header_idx is None:
        # Try fallback: header without MER initially
        for i, ln in enumerate(lines):
            if ln.strip().startswith("| Month | 2025 Orders "):
                header_idx = i
                break
    if header_idx is None:
        print("Monthly Trends table header not found; no changes applied.")
        return

    # Ensure header includes Revenue columns and MER columns (and no trailing extra cell)
    header_line = lines[header_idx].strip()
    if header_line.endswith("|"):
        header_line = header_line[:-1].rstrip()
    if "2025 Revenue" not in header_line:
        header_line = header_line + " | 2025 Revenue | 2024 Revenue | Δ Rev % |"
    # Normalize single trailing pipe
    if not header_line.endswith("|"):
        header_line = header_line + ""
    lines[header_idx] = header_line

    # Rebuild the separator row to have 19 columns (Month left, others right aligned)
    sep = "|---|" + "---:|" * 18
    lines[header_idx + 1] = sep

    # Data rows begin after the separator row (header_idx+1)
    start = header_idx + 2
    # Iterate until next section (line starting with '## ')
    i = start
    while i < len(lines) and not lines[i].startswith("## "):
        ln = lines[i]
        if not ln.strip().startswith("|"):
            i += 1
            continue
        cells = [c.strip() for c in ln.strip().split("|")]
        # Expect first cell empty (leading pipe), month at index 1
        if len(cells) < 5:
            i += 1
            continue
        month_token = cells[1]
        # Only target rows like '2025-01'
        if len(month_token) == 7 and month_token.startswith("2025-"):
            m = month_token
            mer_25 = mer25.get(m, 0.0)
            # Map to prior-year month
            m24 = m.replace("2025", "2024")
            mer_24 = mer24.get(m24, 0.0)
            delta = format_pct_delta(mer_25, mer_24) if mer_24 else "N/A"
            rev_cur = float(rev25.get(m, 0.0))
            rev_prev = float(rev24.get(m24, 0.0))
            rev_delta = format_pct_delta(rev_cur, rev_prev) if rev_prev else "N/A"

            # Ensure row has MER columns at the end; find last three positions
            # Keep all existing columns up to before the final three
            # We'll reconstruct the line with updated MERs
            # Count how many data columns we have by design (16 + 3 MER cols)
            # To be safe, we will rebuild by splitting and replacing the last three values
            parts = ln.split("|")
            # Trim trailing and leading pipe when rejoining
            # Replace last three non-empty positions
            # Normalize parts length
            if len(parts) < 18:
                # Pad to at least 18 to avoid index errors
                parts = parts + [""] * (18 - len(parts))
            # Rebuild row: keep first 16 columns (through Δ MER %), then append revenue columns
            # Extract content columns (strip leading/trailing pipes and blanks)
            content = [c.strip() for c in ln.strip().split('|') if c.strip() != '']
            base_cols = content[:16]
            # Replace MER trio in base_cols (positions 13,14,15 zero-based)
            if len(base_cols) >= 16:
                base_cols[13] = f"{mer_25:.2f}"
                base_cols[14] = f"{mer_24:.2f}"
                base_cols[15] = f"{delta}"
            # Compose new line
            new_ln = "| " + " | ".join(base_cols) + f" | {usd(rev_cur)} | {usd(rev_prev)} | {rev_delta} |"
            # Standardize spacing around pipes
            lines[i] = new_ln
        i += 1

    md_path.write_text("\n".join(lines), encoding="utf-8")


def insert_yoy_mer(md_path: Path, cutoff: datetime | None) -> None:
    lines = md_path.read_text(encoding="utf-8").splitlines()
    # Compute YTD revenue (this year and last year) preferably from existing MD YoY table
    try:
        txt = "\n".join(lines)
        import re
        m = re.search(r"\|\s*Total Revenue\s*\|\s*\$(.*?)\s*\|\s*\$(.*?)\s*\|", txt)
        if m:
            rev_cur = float(str(m.group(1)).replace(',', ''))
            rev_prev = float(str(m.group(2)).replace(',', ''))
        else:
            raise ValueError("YoY revenue not found in MD")
    except Exception:
        # Fallback to Shopify OU CSVs
        try:
            df = pd.read_csv(SHOPIFY_2025_OU)
            df["Day"] = pd.to_datetime(df["Day"], errors="coerce")
            if cutoff is not None:
                df = df[df["Day"] <= cutoff]
            rev_cur = float(pd.to_numeric(df.get("Total sales", 0), errors="coerce").fillna(0).sum())
            rev_prev = 0.0
            prev_col = None
            for cand in ["Total sales (previous_year)", "Total sales (previous year)", "Total sales prev year"]:
                if cand in df.columns:
                    prev_col = cand
                    break
            if prev_col:
                rev_prev = float(pd.to_numeric(df[prev_col], errors="coerce").fillna(0).sum())
        except Exception:
            rev_cur = 0.0
            rev_prev = 0.0

    # Compute YTD spend (this year NB cash, last year historical up to end month)
    # Prefer spend from the MD executive bullet if present
    spend_cur = 0.0
    try:
        import re
        md_text = "\n".join(lines)
        m = re.search(r"Total Spend .*?:\s*\$(\d[\d,]*)\s*\(2025\)\s*/\s*\$(\d[\d,]*)\s*\(2024\)", md_text)
        if m:
            spend_cur = float(m.group(1).replace(',', ''))
            spend_prev = float(m.group(2).replace(',', ''))
        else:
            raise ValueError("Exec spend line not found")
    except Exception:
        try:
            df_nb = pd.read_csv(NB_2025_CSV, usecols=["date", "spend", "accounting_mode"], low_memory=False)
            df_nb["date"] = pd.to_datetime(df_nb["date"], errors="coerce")
            mask = df_nb["date"].notna()
            if cutoff is not None:
                mask &= df_nb["date"] <= cutoff
            df_nb = df_nb[mask]
            if "accounting_mode" in df_nb.columns:
                am = df_nb["accounting_mode"].astype(str).str.lower().str.strip()
                df_nb = df_nb[am.str.contains("cash", na=False)]
            spend_cur = float(pd.to_numeric(df_nb["spend"], errors="coerce").fillna(0).sum())
        except Exception:
            spend_cur = 0.0

    try:
        # If not obtained from MD bullet above
        if 'spend_prev' not in locals():
            hsp = parse_historical_total_spend(HISTORICAL_SPEND_2024)
            if cutoff is not None:
                end_month = f"{cutoff.year-1}-{cutoff.month:02d}"
                # Approximate partial month by excluding current month for previous year
                hsp = hsp[hsp["month"] < end_month]
            spend_prev = float(pd.to_numeric(hsp["total_spend"], errors="coerce").fillna(0).sum())
    except Exception:
        spend_prev = 0.0

    mer_cur = (rev_cur / spend_cur) if spend_cur > 0 else 0.0
    mer_prev = (rev_prev / spend_prev) if spend_prev > 0 else 0.0
    yoy = format_pct_delta(mer_cur, mer_prev) if mer_prev else "N/A"

    # Locate YoY table
    yoy_idx = None
    for i, ln in enumerate(lines):
        if ln.strip().startswith("## Year-over-Year Business Impact"):
            yoy_idx = i
            break
    if yoy_idx is None:
        return
    # Find end of table (next '## ' or end)
    j = yoy_idx + 1
    last_row_idx = None
    while j < len(lines) and not lines[j].startswith("## "):
        if lines[j].startswith("| ") and "|" in lines[j]:
            last_row_idx = j
        j += 1
    if last_row_idx is None:
        return
    # If MER row already exists, replace it
    for k in range(yoy_idx, j):
        if lines[k].startswith("| MER "):
            lines[k] = f"| MER | {mer_cur:.2f} | {mer_prev:.2f} | {yoy} |"
            md_path.write_text("\n".join(lines), encoding="utf-8")
            return
    # Else insert after last_row_idx
    lines.insert(last_row_idx + 1, f"| MER | {mer_cur:.2f} | {mer_prev:.2f} | {yoy} |")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def update_exec_and_yoy_revenue(md_path: Path, cutoff: datetime | None) -> None:
    lines = md_path.read_text(encoding='utf-8').splitlines()
    # Compute YTD revenues from OU
    cur = 0.0
    prev = 0.0
    try:
        df = pd.read_csv(SHOPIFY_2025_OU)
        df['Day'] = pd.to_datetime(df['Day'], errors='coerce')
        df = df.dropna(subset=['Day'])
        if cutoff is not None:
            df = df[df['Day'] <= cutoff]
        cur = float(pd.to_numeric(df['Total sales'], errors='coerce').fillna(0).sum()) if 'Total sales' in df.columns else 0.0
        prev_col = None
        for cand in ["Total sales (previous_year)", "Total sales (previous year)", "Total sales prev year"]:
            if cand in df.columns:
                prev_col = cand
                break
        if prev_col:
            prev = float(pd.to_numeric(df[prev_col], errors='coerce').fillna(0).sum())
    except Exception:
        pass

    # Update exec summary revenue line
    for i, ln in enumerate(lines):
        if ln.strip().startswith('- Total Revenue (Shopify Net):'):
            lines[i] = f"- Total Revenue (Shopify Net): {usd(cur)}"
            break

    # Update YoY Total Revenue row in the YoY table
    for i, ln in enumerate(lines):
        if ln.strip().startswith('| Total Revenue |') and '| YoY Change |' not in lines[i-1] if i>0 else True:
            yoy = format_pct_delta(cur, prev) if prev else 'N/A'
            lines[i] = f"| Total Revenue | {usd(cur)} | {usd(prev)} | {yoy} |"
            break

    # Update MER in exec summary (Revenue / 2025 NB Spend)
    # Try to read 2025 NB Spend from exec line; else recompute from NB CSV
    spend_2025 = 0.0
    try:
        import re
        text = "\n".join(lines)
        m = re.search(r"Total Spend .*?: \$(\d[\d,]*) \(2025\)", text)
        if m:
            spend_2025 = float(m.group(1).replace(',', ''))
        else:
            raise ValueError
    except Exception:
        try:
            df_nb = pd.read_csv(NB_2025_CSV, usecols=['date','spend','accounting_mode'], low_memory=False)
            df_nb['date'] = pd.to_datetime(df_nb['date'], errors='coerce')
            mask = df_nb['date'].notna()
            if cutoff is not None:
                mask &= df_nb['date'] <= cutoff
            df_nb = df_nb[mask]
            if 'accounting_mode' in df_nb.columns:
                am = df_nb['accounting_mode'].astype(str).str.lower().str.strip()
                df_nb = df_nb[am.str.contains('cash', na=False)]
            spend_2025 = float(pd.to_numeric(df_nb['spend'], errors='coerce').fillna(0).sum())
        except Exception:
            spend_2025 = 0.0

    mer = (cur / spend_2025) if spend_2025 else 0.0
    for i, ln in enumerate(lines):
        if ln.strip().startswith('- MER (Shopify Rev / 2025 NB Spend):'):
            lines[i] = f"- MER (Shopify Rev / 2025 NB Spend): {mer:.2f}"
            break

    md_path.write_text("\n".join(lines), encoding='utf-8')


def main() -> None:
    tables = compute_mer_tables()
    mer25 = tables["mer25"]
    mer24 = tables["mer24"]
    rev25 = tables["rev25"]
    rev24 = tables["rev24"]
    update_md_table(MD_PATH, mer25, mer24, rev25, rev24)
    cutoff = read_cutoff_from_md(MD_PATH)
    insert_yoy_mer(MD_PATH, cutoff)
    update_exec_and_yoy_revenue(MD_PATH, cutoff)
    # Print summary for visibility
    out = {}
    for m in sorted(k for k in mer25.keys() if k.startswith("2025-")):
        m24 = m.replace("2025", "2024")
        a = float(mer25.get(m, 0.0))
        b = float(mer24.get(m24, 0.0))
        out[m] = {
            "mer_2025": round(a, 4),
            "mer_2024": round(b, 4),
            "delta_pct": None if b == 0 else round((a - b) / b * 100, 4),
        }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()


