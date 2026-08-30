"""
Generate realistic sample CPG retail data for testing the Perfect Store pipeline.
"""

import os
import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def generate_sample_data(output_path: str, n_rows: int = 2000):
    """Generate a CSV with realistic CPG trade data."""
    random.seed(42)
    np.random.seed(42)

    retailers = [
        "Walmart", "Carrefour", "Tesco", "Costco", "Kroger",
        "7-Eleven", "Circle K", "Walgreens", "CVS", "Dollar General",
        "Aldi", "Lidl", "Metro", "Makro", "Oxxo",
        "FamilyMart", "Lawson", "Wawa", "Sheetz", "QuikTrip",
        "HEB", "Publix", "Meijer", "Target", "Safeway",
        "AM/PM", "Shell Select", "BP Connect", "Chevron ExtraMile", "Casey's",
    ]

    skus = {
        "Cola Classic 330ml Can": "Carbonated Soft Drinks",
        "Cola Classic 2L Bottle": "Carbonated Soft Drinks",
        "Citrus Surge 330ml": "Carbonated Soft Drinks",
        "Hydra Sport 600ml": "Sports Drinks",
        "Hydra Sport 1L": "Sports Drinks",
        "SunPress OJ 1.5L": "Juice",
        "SunPress Apple 1.5L": "Juice",
        "CrunchBite Classic 280g": "Salty Snacks",
        "CrunchBite BBQ 280g": "Salty Snacks",
        "TortoChips Nacho 300g": "Salty Snacks",
        "TortoChips Original 360g": "Salty Snacks",
        "PuffKing Crunchy 225g": "Salty Snacks",
        "GrainMill Oats 1.2kg": "Breakfast",
        "CerealCo Honey Crunch 400g": "Breakfast",
        "AquaPure 500ml": "Water",
        "AquaPure 1L": "Water",
        "Cola Zero 330ml Can": "Carbonated Soft Drinks",
        "Lemon Zest 330ml": "Carbonated Soft Drinks",
        "PowerRush Energy 500ml": "Energy Drinks",
        "VitaWater Enhanced 600ml": "Enhanced Water",
    }

    regions = ["Northeast", "Southeast", "Midwest", "West", "Southwest"]
    channels = ["Modern Trade", "Traditional Trade", "Convenience", "E-commerce", "Gas/Petrol"]

    # Assign each retailer a primary channel and region (with some variation)
    retailer_profiles = {}
    for r in retailers:
        retailer_profiles[r] = {
            "primary_channel": random.choice(channels),
            "primary_region": random.choice(regions),
            "volume_multiplier": np.random.lognormal(0, 0.8),  # some retailers are bigger
        }

    # Date range: last 12 months
    end_date = datetime(2026, 3, 31)
    start_date = end_date - timedelta(days=365)

    rows = []
    for _ in range(n_rows):
        retailer = random.choice(retailers)
        profile = retailer_profiles[retailer]
        sku_name = random.choice(list(skus.keys()))
        category = skus[sku_name]

        # Date with more recent dates weighted heavier
        days_ago = int(np.random.exponential(90))
        days_ago = min(days_ago, 365)
        date = end_date - timedelta(days=days_ago)

        # Channel: mostly their primary, some variation
        channel = (profile["primary_channel"] if random.random() < 0.7
                   else random.choice(channels))
        region = (profile["primary_region"] if random.random() < 0.8
                  else random.choice(regions))

        # Volume and revenue
        base_volume = random.randint(10, 500)
        volume = int(base_volume * profile["volume_multiplier"])
        unit_price = round(random.uniform(1.5, 8.0), 2)
        revenue = round(volume * unit_price, 2)
        frequency = random.randint(1, 20)

        rows.append({
            "date": date.strftime("%Y-%m-%d"),
            "retailer": retailer,
            "sku": sku_name,
            "category": category,
            "region": region,
            "channel": channel,
            "volume_units": volume,
            "revenue": revenue,
            "frequency": frequency,
        })

    df = pd.DataFrame(rows)

    # Inject some realistic DQ issues for testing
    # 1. A few null values
    null_indices = random.sample(range(len(df)), 15)
    for idx in null_indices[:5]:
        df.loc[idx, "sku"] = None
    for idx in null_indices[5:10]:
        df.loc[idx, "revenue"] = None
    for idx in null_indices[10:]:
        df.loc[idx, "region"] = None

    # 2. One SKU under two categories (DQ issue)
    mask = df["sku"] == "CrunchBite Classic 280g"
    flip_indices = df[mask].sample(n=min(3, mask.sum()), random_state=42).index
    df.loc[flip_indices, "category"] = "Snack Foods"  # should be "Salty Snacks"

    # 3. One volume outlier retailer
    df.loc[df["retailer"] == "Walmart", "volume_units"] *= 15

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Generated {len(df)} rows of sample CPG data → {output_path}")
    return df


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "inbox/sample_cpg_data.csv"
    generate_sample_data(path)
