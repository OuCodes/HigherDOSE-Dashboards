import csv
import datetime as dt
from collections import defaultdict
from pathlib import Path


# Resolve repo root relative to this script so paths are portable
DATA_DIR = Path(__file__).resolve().parents[1] / 'data'


def parse_date(value: str) -> dt.date:
    return dt.datetime.strptime(value.strip(), '%Y-%m-%d').date()


def parse_money(value: str) -> float:
    if value is None:
        return 0.0
    v = str(value).replace('$', '').replace(',', '').strip()
    if v == '':
        return 0.0
    try:
        return float(v)
    except Exception:
        return 0.0


def iso_week(date_obj: dt.date) -> int:
    return date_obj.isocalendar().week


def load_meta_2024_q4_daily() -> dict:
    path = DATA_DIR / 'ads/q4-planning-2025/ads/meta-ads-2024Q4-daily.csv'
    weekly = defaultdict(lambda: {'spend': 0.0, 'rev': 0.0})
    total_spend = 0.0
    total_rev = 0.0
    with path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            day = row.get('Day') or row.get('Reporting starts')
            try:
                d = parse_date(day)
            except Exception:
                continue
            if d.year != 2024 or d.month not in (10, 11, 12):
                continue
            spend = parse_money(row.get('Amount spent (USD)') or row.get('Amount Spent (USD)') or row.get('Amount spent'))
            rev = parse_money(row.get('Purchases conversion value') or row.get('Purchase conversion value'))
            w = iso_week(d)
            weekly[w]['spend'] += spend
            weekly[w]['rev'] += rev
            total_spend += spend
            total_rev += rev
    return {
        'weekly': {w: {
            'spend': v['spend'],
            'rev': v['rev'],
            'roas': (v['rev'] / v['spend']) if v['spend'] else None,
        } for w, v in sorted(weekly.items())},
        'total': {
            'spend': total_spend,
            'rev': total_rev,
            'roas': (total_rev / total_spend) if total_spend else None,
        }
    }


def _iter_google_rows_with_header(path: Path):
    """Yield rows from a Google Ads CSV, skipping preface lines until the header with 'Day' is found."""
    with path.open('r', encoding='utf-8') as f:
        lines = f.read().splitlines()
    # Find header index containing 'Account name' and 'Day'
    header_idx = None
    for i, line in enumerate(lines):
        if 'Account name' in line and ',Day,' in line:
            header_idx = i
            break
    if header_idx is None:
        # Fallback: try line containing 'Day,'
        for i, line in enumerate(lines):
            if line.startswith('Day,'):
                header_idx = i
                break
    if header_idx is None:
        return []
    reader = csv.DictReader(lines[header_idx:])
    return list(reader)


def load_google_2024_q4_daily() -> dict:
    path = DATA_DIR / 'ads/q4-planning-2025/ads/google-ads-2024Q4-daily.csv'
    weekly = defaultdict(lambda: {'spend': 0.0, 'rev': 0.0})
    total_spend = 0.0
    total_rev = 0.0
    for row in _iter_google_rows_with_header(path):
        day = row.get('Day')
        try:
            d = parse_date(day)
        except Exception:
            continue
        if d.year != 2024 or d.month not in (10, 11, 12):
            continue
        spend = parse_money(row.get('Cost') or row.get('Cost (Converted currency)'))
        rev = parse_money(row.get('Conv. value'))
        w = iso_week(d)
        weekly[w]['spend'] += spend
        weekly[w]['rev'] += rev
        total_spend += spend
        total_rev += rev
    return {
        'weekly': {w: {
            'spend': v['spend'],
            'rev': v['rev'],
            'roas': (v['rev'] / v['spend']) if v['spend'] else None,
        } for w, v in sorted(weekly.items())},
        'total': {
            'spend': total_spend,
            'rev': total_rev,
            'roas': (total_rev / total_spend) if total_spend else None,
        }
    }


def load_meta_2025_recent() -> dict:
    # Aug 24–Sep 22, 2025
    path = DATA_DIR / 'ads/meta-mtd-export-aug-24-2025-to-sep-22-2025.auto.csv'
    total_spend = 0.0
    total_rev = 0.0
    with path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            day = row.get('Day') or row.get('Reporting starts')
            try:
                d = parse_date(day)
            except Exception:
                continue
            if not (dt.date(2025, 8, 24) <= d <= dt.date(2025, 9, 22)):
                continue
            total_spend += parse_money(row.get('Amount spent (USD)') or row.get('Amount Spent (USD)') or row.get('Amount spent'))
            total_rev += parse_money(row.get('Purchases conversion value') or row.get('Purchase conversion value'))
    return {
        'total': {
            'spend': total_spend,
            'rev': total_rev,
            'roas': (total_rev / total_spend) if total_spend else None,
        }
    }


def load_google_2025_recent() -> dict:
    path = DATA_DIR / 'ads/google-mtd-export-aug-23-to-sep-21-2025-account-level-daily report.csv.csv'
    total_spend = 0.0
    total_rev = 0.0
    for row in _iter_google_rows_with_header(path):
        day = row.get('Day')
        try:
            d = parse_date(day)
        except Exception:
            continue
        if not (dt.date(2025, 8, 23) <= d <= dt.date(2025, 9, 21)):
            continue
        total_spend += parse_money(row.get('Cost') or row.get('Cost (Converted currency)'))
        total_rev += parse_money(row.get('Conv. value'))
    return {
        'total': {
            'spend': total_spend,
            'rev': total_rev,
            'roas': (total_rev / total_spend) if total_spend else None,
        }
    }


def load_projections() -> dict:
    path = DATA_DIR / "ads/Q4 Projections - Sheet1.csv"
    weeks = {}
    header_found = False
    with path.open('r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            if not header_found and len(row) >= 2 and row[0].strip() == 'Week of Year':
                header_found = True
                continue
            if not header_found:
                continue
            # Stop at TOTAL rows or empty week
            if row[0].strip() == '' or row[0].strip().upper() in {'TOTAL Q4', 'TOTAL'}:
                break
            # Expect numeric week
            try:
                week = int(row[0])
            except Exception:
                continue
            # Fixed column layout per provided sheet
            meta_sales = parse_money(row[6] if len(row) > 6 else '')
            meta_spend = parse_money(row[7] if len(row) > 7 else '')
            goog_sales = parse_money(row[9] if len(row) > 9 else '')
            goog_spend = parse_money(row[10] if len(row) > 10 else '')
            weeks[week] = {
                'meta': {
                    'sales': meta_sales,
                    'spend': meta_spend,
                    'roas': (meta_sales / meta_spend) if meta_spend else None,
                },
                'google': {
                    'sales': goog_sales,
                    'spend': goog_spend,
                    'roas': (goog_sales / goog_spend) if goog_spend else None,
                },
            }
    return weeks


def pct_diff(a: float, b: float) -> float:
    if a is None or b is None or a == 0:
        return float('inf')
    return (b - a) / a


def main() -> None:
    proj = load_projections()
    meta24 = load_meta_2024_q4_daily()
    goog24 = load_google_2024_q4_daily()
    meta25 = load_meta_2025_recent()
    goog25 = load_google_2025_recent()

    print('2025 in-platform recent ROAS (Aug 24–Sep 22):')
    m_roas = meta25['total']['roas']
    g_roas = goog25['total']['roas']
    print(f"  Meta:   spend=${meta25['total']['spend']:.0f}, rev=${meta25['total']['rev']:.0f}, ROAS={(f'{m_roas:.2f}' if m_roas is not None else 'n/a')}")
    print(f"  Google: spend=${goog25['total']['spend']:.0f}, rev=${goog25['total']['rev']:.0f}, ROAS={(f'{g_roas:.2f}' if g_roas is not None else 'n/a')}")
    print()

    print('2024 Q4 in-platform totals:')
    print(f"  Meta:   spend=${meta24['total']['spend']:.0f}, rev=${meta24['total']['rev']:.0f}, ROAS={meta24['total']['roas']:.2f}")
    print(f"  Google: spend=${goog24['total']['spend']:.0f}, rev=${goog24['total']['rev']:.0f}, ROAS={goog24['total']['roas']:.2f}")
    print()

    print('Weekly gut check vs projections (ROAS deltas > 20% flagged):')
    for week in sorted(proj.keys()):
        p = proj[week]
        m24 = meta24['weekly'].get(week)
        g24 = goog24['weekly'].get(week)
        # Only show weeks present in 2024 Q4
        if not m24 and not g24:
            continue
        msgs = []
        if m24 and p['meta']['roas'] is not None and m24['roas']:
            d = pct_diff(m24['roas'], p['meta']['roas'])
            if abs(d) > 0.2:
                msgs.append(f"Meta ROAS proj {p['meta']['roas']:.2f} vs 2024 {m24['roas']:.2f} ({d:+.0%})")
        if g24 and p['google']['roas'] is not None and g24['roas']:
            d = pct_diff(g24['roas'], p['google']['roas'])
            if abs(d) > 0.2:
                msgs.append(f"Google ROAS proj {p['google']['roas']:.2f} vs 2024 {g24['roas']:.2f} ({d:+.0%})")
        if msgs:
            print(f"  W{week}: " + ' | '.join(msgs))

    print()
    print('Note: Projection spend scale may differ from 2024 actuals; compare ROAS primarily.')


if __name__ == '__main__':
    main()


