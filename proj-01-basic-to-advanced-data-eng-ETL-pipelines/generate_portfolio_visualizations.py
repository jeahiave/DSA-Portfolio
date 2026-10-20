import json
import importlib.util
from datetime import date
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'portfolio_visualizations'
OUT.mkdir(parents=True, exist_ok=True)

sns.set_theme(style='whitegrid', context='notebook', font='DejaVu Sans')
BG = '#f5f8f3'
INK = '#132d22'
MUTED = '#587166'
GREEN = '#0b6b4a'
MINT = '#00b889'
LIME = '#d9f178'
GRID = '#dce6dd'
plt.rcParams.update({'figure.facecolor': BG, 'axes.facecolor': BG, 'axes.edgecolor': GRID,
                     'axes.labelcolor': INK, 'text.color': INK, 'xtick.color': MUTED,
                     'ytick.color': MUTED, 'grid.color': GRID, 'font.size': 10,
                     'axes.titleweight': 'bold', 'savefig.facecolor': BG})


def fetch_json(url):
    sys.path.insert(0, str(ROOT))
    from pipeline_utils import http_session
    response = http_session().get(url, timeout=20)
    response.raise_for_status()
    return response.json()


def load_transform(relpath, alias):
    path = ROOT / relpath
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT))
    spec.loader.exec_module(module)
    return module.transform


def save(fig, name):
    fig.savefig(OUT / name, dpi=190, bbox_inches='tight', pad_inches=.18)
    plt.close(fig)

# This flow shows the real extract, transform, and load behaviors in sophistication order.
fig, ax = plt.subplots(figsize=(13, 7.3))
fig.subplots_adjust(left=.20, right=.98, top=.88, bottom=.08)
ax.set_xlim(0, 10); ax.set_ylim(0, 4.65); ax.axis('off')
fig.suptitle('Four pipelines, one dependable data pattern', x=.5, y=.97,
             fontsize=19, color=INK, fontweight='bold')
fig.text(.5, .92, 'Ordered by implementation depth · each lane ends in a typed relational table',
         ha='center', color=MUTED, fontsize=10)
lanes = [
    ('01  MARKET HISTORY', 'Yahoo Finance', 'OHLC + freshness checks', 'Refresh snapshot', 'Prices + chart'),
    ('02  EARTHQUAKE EVENTS', 'USGS GeoJSON', 'Magnitude + coordinate checks', 'Revision-aware upsert', 'Event history'),
    ('03  UNIVERSITY DIRECTORY', 'University API', 'Normalize lists + stable key', 'Deduplicate snapshot', 'Reference table'),
    ('04  EMPLOYEE RECORDS', 'JSONPlaceholder', 'Flatten JSON + required fields', 'Replace snapshot', 'Typed directory'),
]
xs = [0.1, 2.45, 4.8, 7.15]
widths = [1.72, 1.72, 1.72, 1.72]
colors = ['#d8f1e8', '#e5f3dc', '#edf2dc', '#eef1ed']
for i, lane in enumerate(lanes):
    y = 3.5 - i * .95
    ax.text(-.18, y+.28, lane[0], ha='right', va='center', fontsize=9, weight='bold', color=GREEN)
    for j, label in enumerate(lane[1:]):
        box = FancyBboxPatch((xs[j], y), widths[j], .56,
                             boxstyle='round,pad=0.06,rounding_size=.09',
                             linewidth=1, edgecolor='#b4cdbd', facecolor=colors[j], zorder=2)
        ax.add_patch(box)
        ax.text(xs[j]+widths[j]/2, y+.28, label, ha='center', va='center',
                fontsize=8.2, color=INK, wrap=True, zorder=3)
        if j < len(lane)-2:
            ax.add_patch(FancyArrowPatch((xs[j]+widths[j]+.05, y+.28),
                         (xs[j+1]-.06, y+.28), arrowstyle='-|>', mutation_scale=11,
                         linewidth=1.4, color=MINT, zorder=4))
ax.text(.1, .2, 'Shared operations: timeouts · retries · structured logs · migrations · run history · freshness checks',
        color=MUTED, fontsize=9.5, ha='left')
save(fig, 'etl-flow-overview.png')

# 1) Mock employee records, visualizing their nested location coordinates after flattening.
emp_payload = fetch_json('https://jsonplaceholder.typicode.com/users')
employee_transform = load_transform('00-ETL-daily-employee-record-data-pipeline/daily_employee_record.py', 'employee_pipeline')
emp = employee_transform(emp_payload)
fig, ax = plt.subplots(figsize=(9.4, 5.6))
sc = ax.scatter(emp['address_geo_lng'], emp['address_geo_lat'],
                 s=115, c=np.arange(len(emp)), cmap='crest', edgecolors='white', linewidth=1.4, zorder=3)
for row in emp.itertuples():
    ax.annotate(row.city, (row.address_geo_lng, row.address_geo_lat), xytext=(5, 5),
                textcoords='offset points', fontsize=7.3, color=INK)
ax.set_title('Flattened profile locations', loc='left', fontsize=16, pad=16)
ax.set_xlabel('Longitude'); ax.set_ylabel('Latitude')
ax.text(0, 1.02, f'{len(emp)} mock records · nested address coordinates retained as typed fields',
        transform=ax.transAxes, color=MUTED, fontsize=9)
ax.grid(alpha=.75); sns.despine(ax=ax)
fig.text(.01, .005, 'Source: JSONPlaceholder mock user directory · coordinates are sample data, not real employee locations.', color=MUTED, fontsize=8)
save(fig, 'employee-profile-geography.png')

# 2) University directory: profile the list-to-text normalization and reference-key input.
all_unis = fetch_json('https://raw.githubusercontent.com/Hipo/university-domains-list/master/world_universities_and_domains.json')
uk_payload = [row for row in all_unis if row.get('country') == 'United Kingdom']
university_transform = load_transform('01-ETL-global-education-data-pipeline/global_edu.py', 'education_pipeline')
unis = university_transform(uk_payload)
# Count recognized academic domain suffixes in the transformed domain fields.
def domain_suffix(domain):
    host = str(domain).strip().lower().split('@')[-1].split(':')[0]
    if host.startswith('www.'):
        host = host[4:]
    bits = host.split('.')
    return '.' + '.'.join(bits[-2:]) if len(bits) >= 2 else 'other'
counts = {}
for domains in unis['domains']:
    for domain in set(part.strip() for part in str(domains).split(',') if part.strip()):
        suffix = domain_suffix(domain)
        counts[suffix] = counts.get(suffix, 0) + 1
ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:9]
labels = [x[0] for x in ranked][::-1]
values = [x[1] for x in ranked][::-1]
fig, ax = plt.subplots(figsize=(9.4, 5.6))
palette = sns.color_palette(['#0b6b4a', '#0d8e65', '#15aa7c', '#42bd8e', '#71cfa1', '#a1ddb5', '#bedfc0', '#cbd9c8', '#d6dfd6'], n_colors=len(labels))
ax.barh(labels, values, color=palette, height=.66)
for i, value in enumerate(values):
    ax.text(value + max(values)*.015, i, f'{value:,}', va='center', color=INK, fontsize=9, weight='bold')
ax.set_title('Website domain suffixes in the UK directory', loc='left', fontsize=15, pad=14)
ax.set_xlabel('Distinct transformed domain entries'); ax.set_ylabel('Domain suffix')
ax.set_xlim(0, max(values)*1.15 if values else 1)
ax.text(0, 1.02, f'{len(uk_payload)} source rows → {len(unis)} validated unique rows with websites',
        transform=ax.transAxes, color=MUTED, fontsize=9)
ax.grid(axis='x', alpha=.65); ax.grid(axis='y', visible=False); sns.despine(ax=ax, left=True)
fig.text(.01, .005, f'Source: Hipo university domains list, filtered to United Kingdom · current snapshot captured {date.today():%Y-%m-%d}.', color=MUTED, fontsize=8)
save(fig, 'university-directory-domains.png')

# 3) USGS earthquake feed: magnitude and geographic distribution after the project's M3 filter.
quake_payload = fetch_json('https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson')
earthquake_transform = load_transform('02-ETL-global-earthquake-data-pipeline/global_earthquake.py', 'earthquake_pipeline')
quakes = earthquake_transform(quake_payload, threshold=3.0)
fig, ax = plt.subplots(figsize=(10, 5.9))
if len(quakes):
    points = ax.scatter(quakes['longitude'], quakes['latitude'],
        c=quakes['magnitude'], s=np.clip((quakes['magnitude']-2.4)**2*9, 18, 180),
        cmap='mako', alpha=.78, edgecolors='white', linewidth=.35)
    cb = fig.colorbar(points, ax=ax, pad=.02); cb.set_label('Magnitude')
ax.set_xlim(-180, 180); ax.set_ylim(-90, 90)
ax.set_xlabel('Longitude'); ax.set_ylabel('Latitude')
ax.set_title('Earthquakes that pass the M3 load threshold', loc='left', fontsize=15, pad=14)
ax.text(0, 1.02, f'{len(quakes):,} qualifying events · marker size scales with magnitude',
        transform=ax.transAxes, color=MUTED, fontsize=9)
ax.grid(alpha=.6); sns.despine(ax=ax)
fig.text(.01, .005, f'Source: USGS all-week GeoJSON feed · captured {date.today():%Y-%m-%d} · each plotted point is keyed by USGS event ID.', color=MUTED, fontsize=8)
save(fig, 'earthquake-event-map.png')

# 4) Apple market history: actual fetched daily closes and volumes, the pipeline's analytical output.
import yfinance as yf
stock = yf.Ticker('AAPL').history(period='1mo', interval='1d')
if stock.empty:
    raise ValueError('Yahoo Finance returned no AAPL rows')
stock.columns = [str(c).lower().replace(' ', '_') for c in stock.columns]
if 'close' not in stock.columns:
    raise ValueError('Downloaded stock file has no close column')
stock = stock.dropna(subset=['close']).sort_index()
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6.2), sharex=True,
                               gridspec_kw={'height_ratios':[3.2, 1]}, constrained_layout=True)
close = stock['close'].astype(float)
ax1.plot(stock.index, close, color=GREEN, linewidth=2.6, marker='o', markersize=4.5)
ax1.fill_between(stock.index, close.to_numpy(), close.min()*.996, color=MINT, alpha=.14)
ax1.scatter([stock.index[-1]], [close.iloc[-1]], s=65, color=LIME, edgecolors=GREEN, linewidth=1.2, zorder=5)
ax1.annotate(f'${close.iloc[-1]:,.2f}', (stock.index[-1], close.iloc[-1]), xytext=(-8, 14),
             textcoords='offset points', ha='right', fontsize=9, weight='bold', color=GREEN)
ax1.set_title('AAPL close and trading volume', loc='left', fontsize=15, pad=12)
ax1.set_ylabel('Close (USD)'); ax1.grid(axis='y', alpha=.7); ax1.grid(axis='x', visible=False)
vol = stock['volume'] if 'volume' in stock.columns else pd.Series(0, index=stock.index)
ax2.bar(stock.index, vol, color='#76b99b', width=.7)
ax2.set_ylabel('Volume'); ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
ax2.grid(axis='y', alpha=.7); ax2.grid(axis='x', visible=False)
for ax in (ax1,ax2): sns.despine(ax=ax)
change = (close.iloc[-1] / close.iloc[0] - 1) * 100
ax1.text(0, 1.02, f'{len(stock)} trading sessions · {stock.index.min():%b %d}–{stock.index.max():%b %d, %Y} · period change {change:+.1f}%',
         transform=ax1.transAxes, color=MUTED, fontsize=9)
fig.text(.01, -.015, f'Source: Yahoo Finance via yfinance · 1 month of daily history retrieved {date.today():%Y-%m-%d} · descriptive only.', color=MUTED, fontsize=8)
save(fig, 'market-price-volume.png')

print(f'employee_rows={len(emp)} university_source={len(uk_payload)} university_valid={len(unis)} earthquake_events={len(quakes)} stock_sessions={len(stock)}')
print('assets:', ', '.join(p.name for p in sorted(OUT.glob('*.png'))))
