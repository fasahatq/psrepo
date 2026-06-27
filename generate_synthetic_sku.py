import pandas as pd
import numpy as np

np.random.seed(42)

# ── Load source files ────────────────────────────────────────────────────────
sku_df   = pd.read_csv('/home/fasahatq/perfect-store/inbox/Cust_SKU_Data.csv')
market_df = pd.read_csv('/home/fasahatq/perfect-store/inbox/Market_Master_File.csv')

store_ids = market_df['OUTLET_UID_EDITED'].astype(str).tolist()
n_stores  = len(store_ids)
print(f"Outlets from Market_Master_File : {n_stores}")

# ── Build SKU combo table with reference penetration rates ───────────────────
# Penetration in Cust_SKU_Data = fraction of its 5 reference outlets that carry
# each SKU.  We will map those reference rates onto a smooth probability range
# so the synthetic data scales naturally to 10 000 outlets.
n_ref_outlets = sku_df['CUST_UNIQ_ID_VAL'].nunique()   # 5

valid = sku_df.dropna(subset=['BRND_NM']).copy()
sku_combos = (
    valid
    .groupby(['BRND_NM', 'SUB_BRND_NM', 'FLVR_NM', 'PPG_DESC'])
    .size()
    .reset_index(name='ref_count')
    .sort_values('ref_count', ascending=False)
    .reset_index(drop=True)
)
sku_combos['ref_pct'] = sku_combos['ref_count'] / n_ref_outlets  # 1.0 / 0.8 / 0.6 …

# Map each reference-penetration tier to a realistic probability range for
# the synthetic dataset.  Ranges are chosen so the final distribution has:
#   ~few SKUs at 90 %+, a band at 80–90 %, and a long tail of lower-reach SKUs.
TIER_MAP = {
    1.00: (0.88, 0.97),   # "must-stock" SKUs → 88–97 % of all outlets
    0.80: (0.72, 0.88),   # strong SKUs      → 72–88 %
    0.60: (0.50, 0.72),   # good SKUs        → 50–72 %
    0.40: (0.28, 0.50),   # moderate SKUs    → 28–50 %
    0.20: (0.07, 0.28),   # niche SKUs       →  7–28 %
}

def _assign_prob(ref_pct):
    lo, hi = TIER_MAP.get(round(ref_pct, 2), (0.05, 0.15))
    return float(np.random.uniform(lo, hi))

sku_combos['dist_prob'] = sku_combos['ref_pct'].apply(_assign_prob)

print(f"SKU combos          : {len(sku_combos)}")
print("\nDistribution probability summary by tier:")
for ref, grp in sku_combos.groupby('ref_pct'):
    print(f"  ref {int(ref*100):3d}% → synthetic "
          f"{grp['dist_prob'].min()*100:.1f}–{grp['dist_prob'].max()*100:.1f}%  "
          f"({len(grp)} SKUs)")

# ── NET_SALES parameters (log-normal) per BRND × PPG ────────────────────────
# Fitted from Cust_SKU_Data.  Where only 1 sample exists we use the PPG-level
# std as a fallback so we still get realistic variance.
ppg_std = {}
for ppg, grp in valid.dropna(subset=['NET_SALES']).groupby('PPG_DESC'):
    vals = np.log(grp['NET_SALES'].clip(lower=0.01))
    ppg_std[ppg] = float(vals.std()) if len(vals) > 1 else 1.2

net_sales_params = {}   # (mu, sigma) keyed by (BRND_NM, PPG_DESC)
for (brnd, ppg), grp in valid.dropna(subset=['NET_SALES']).groupby(['BRND_NM', 'PPG_DESC']):
    vals = np.log(grp['NET_SALES'].clip(lower=0.01))
    mu    = float(vals.mean())
    sigma = float(vals.std()) if len(vals) > 1 else ppg_std.get(ppg, 1.2)
    net_sales_params[(brnd, ppg)] = (mu, sigma)

# Fallback for any unseen brand-PPG
all_log        = np.log(valid['NET_SALES'].dropna().clip(lower=0.01))
fallback_mu    = float(all_log.mean())
fallback_sigma = float(all_log.std())

# ── Generate synthetic records ───────────────────────────────────────────────
# Each outlet gets an outlet-level sales multiplier so that some outlets are
# big (high NET_SALES) and some are small, adding natural heterogeneity.
outlet_scale_log = np.random.normal(0, 0.4, n_stores)  # log-scale shift per store

records = []
for i, store_id in enumerate(store_ids):
    store_shift = outlet_scale_log[i]
    for _, sku in sku_combos.iterrows():
        # Decide whether this outlet carries this SKU
        if np.random.random() > sku['dist_prob']:
            continue
        brnd = sku['BRND_NM']
        ppg  = sku['PPG_DESC']
        mu, sigma = net_sales_params.get((brnd, ppg), (fallback_mu, fallback_sigma))
        # Log-normal draw, shifted by the outlet-level factor
        net_sales = round(np.exp(np.random.normal(mu + store_shift, sigma * 0.6)), 4)
        net_sales = max(0.01, net_sales)
        records.append({
            'CUST_UNIQ_ID_VAL': store_id,
            'BRND_NM'         : brnd,
            'SUB_BRND_NM'     : sku['SUB_BRND_NM'],
            'FLVR_NM'         : sku['FLVR_NM'],
            'PPG_DESC'        : ppg,
            'NET_SALES'       : net_sales,
        })

out_df = pd.DataFrame(
    records,
    columns=['CUST_UNIQ_ID_VAL', 'BRND_NM', 'SUB_BRND_NM', 'FLVR_NM', 'PPG_DESC', 'NET_SALES'],
)

# ── Save ─────────────────────────────────────────────────────────────────────
out_path = '/home/fasahatq/perfect-store/inbox/India_Synthetic_SKU_Data.csv'
out_df.to_csv(out_path, index=False)

# ── Summary ──────────────────────────────────────────────────────────────────
print(f"\nRows generated      : {len(out_df):,}")
print(f"Outlets covered     : {out_df['CUST_UNIQ_ID_VAL'].nunique():,}")
print(f"Saved to            : {out_path}")

skus_per_outlet = out_df.groupby('CUST_UNIQ_ID_VAL').size()
print(f"\nSKUs per outlet     : min={skus_per_outlet.min()}, "
      f"median={skus_per_outlet.median():.0f}, "
      f"mean={skus_per_outlet.mean():.1f}, "
      f"max={skus_per_outlet.max()}")

# Actual penetration achieved vs target
print("\nActual SKU penetration across all outlets:")
actual_pen = out_df.groupby(['BRND_NM','SUB_BRND_NM','FLVR_NM','PPG_DESC'])\
                   ['CUST_UNIQ_ID_VAL'].nunique().reset_index(name='outlets_with_sku')
actual_pen['pct'] = (actual_pen['outlets_with_sku'] / n_stores * 100).round(1)
actual_pen = actual_pen.merge(
    sku_combos[['BRND_NM','SUB_BRND_NM','FLVR_NM','PPG_DESC','ref_pct','dist_prob']],
    on=['BRND_NM','SUB_BRND_NM','FLVR_NM','PPG_DESC']
).sort_values('pct', ascending=False)
print(actual_pen[['BRND_NM','PPG_DESC','FLVR_NM','dist_prob','pct']].to_string(index=False))

print("\nNET_SALES stats:")
print(out_df['NET_SALES'].describe())
