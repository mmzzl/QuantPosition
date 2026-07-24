import pandas as pd
df = pd.read_csv('data/all_stock.csv')
print('tradeStatus values:', df['tradeStatus'].unique())

idx = df[df['code_name'].str.contains('指数|指', na=False)]
print(f'Index-like names: {len(idx)}')
for _, r in idx.head(3).iterrows():
    print(f'  {r["code"]} {r["code_name"]} status={r["tradeStatus"]}')

for prefix in ['300', '688']:
    subset = df[df['code'].str.contains(f's[hz].{prefix}', na=False)]
    print(f'{prefix}xxx stocks: {len(subset)}')

st = df[df['code_name'].str.contains('ST|退', na=False)]
print(f'ST stocks: {len(st)}')

# Check total real stocks (by typical A-share code patterns)
import re
pattern = r's[hz]\.\d{6}$'
stocks = df[df['code'].str.match(pattern)]
print(f'Total SH/SZ codes: {len(stocks)}')
