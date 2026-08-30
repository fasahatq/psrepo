import pandas as pd

# Market_Master_File.csv is already compact (~10 000 rows); no trimming needed.
in_path  = "inbox/Market_Master_File.csv"
out_path = "inbox/Market_Master_File.csv"

df = pd.read_csv(in_path)
df.to_csv(out_path, index=False)
print(f"Market_Master_File loaded and resaved: {len(df):,} outlets")