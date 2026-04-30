"""Generate the sample CSV that ships with the repo for offline demos."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from helleniflex import make_synthetic_greek_dam_prices

prices = make_synthetic_greek_dam_prices(start="2024-01-01", end="2025-12-31")
out = ROOT / "data" / "sample_dam_prices.csv"
prices.to_frame("price_eur_mwh").to_csv(out, index_label="timestamp")
print(f"Wrote {len(prices):,} rows → {out}")
