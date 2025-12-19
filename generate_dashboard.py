#!/usr/bin/env python3
"""Generate self-contained HTML dashboard with embedded images"""

import json
import base64
import pandas as pd
import altair as alt
import re
from collections import Counter
from pathlib import Path
from datetime import datetime

alt.data_transformers.disable_max_rows()

DATA_FILE = 'data/error-jobs-sanitized.json.gz'

print("Loading data...")
import gzip
with gzip.open(DATA_FILE, 'rt', encoding='utf-8') as f:
    raw_data = json.load(f)

df = pd.DataFrame(raw_data)
print(f"Loaded {len(df):,} records")

# Parse timestamps
df['create_time'] = pd.to_datetime(df['create_time'], format='ISO8601')
df['date'] = df['create_time'].dt.date
df['hour'] = df['create_time'].dt.hour
df['day_of_week'] = df['create_time'].dt.day_name()

# Extract tool name
def get_tool_name(tool_id):
    if not tool_id or pd.isna(tool_id):
        return 'unknown'
    parts = str(tool_id).split('/')
    return parts[3] if len(parts) >= 4 else str(tool_id)

df['tool_name'] = df['tool_id'].apply(get_tool_name)

# Generate charts and convert to base64
def chart_to_base64(chart):
    png_data = chart.to_dict()
    # Save to PNG and encode
    import io
    png_bytes = io.BytesIO()
    chart.save(png_bytes, format='png', scale_factor=2)
    png_bytes.seek(0)
    return base64.b64encode(png_bytes.read()).decode('utf-8')

print("Generating charts...")

charts = {}

# 1. Top 20 failing tools
tool_counts = df['tool_name'].value_counts().head(20).reset_index()
tool_counts.columns = ['tool', 'count']
charts['top_tools'] = alt.Chart(tool_counts).mark_bar(color='#4a90d9').encode(
    x=alt.X('count:Q', title='Error Count'),
    y=alt.Y('tool:N', sort='-x', title='Tool'),
    tooltip=['tool', 'count']
).properties(title='Top 20 Failing Tools', width=500, height=400)

# 2. Exit codes
exit_counts = df['exit_code'].fillna('None').astype(str).value_counts().head(12).reset_index()
exit_counts.columns = ['exit_code', 'count']
charts['exit_codes'] = alt.Chart(exit_counts).mark_bar().encode(
    x=alt.X('exit_code:N', sort='-y', title='Exit Code'),
    y=alt.Y('count:Q', title='Count'),
    color=alt.condition(alt.datum.exit_code == '0', alt.value('#e74c3c'), alt.value('#4a90d9')),
    tooltip=['exit_code', 'count']
).properties(title='Exit Code Distribution', width=500, height=250)

# 3. Destinations
dest_counts = df['destination_id'].fillna('None').value_counts().reset_index()
dest_counts.columns = ['destination', 'count']
charts['destinations'] = alt.Chart(dest_counts).mark_bar(color='#27ae60').encode(
    x=alt.X('count:Q', title='Error Count'),
    y=alt.Y('destination:N', sort='-x', title='Destination'),
    tooltip=['destination', 'count']
).properties(title='Failures by Destination', width=500, height=350)

# 4. Daily trend
daily = df.groupby('date').size().reset_index(name='count')
daily['date'] = pd.to_datetime(daily['date'])
charts['daily'] = alt.Chart(daily).mark_line(point=True, color='#e67e22').encode(
    x=alt.X('date:T', title='Date'),
    y=alt.Y('count:Q', title='Error Count'),
    tooltip=['date:T', 'count:Q']
).properties(title='Daily Error Count', width=650, height=250)

# 5. Day of week
dow_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
dow_counts = df['day_of_week'].value_counts().reindex(dow_order).reset_index()
dow_counts.columns = ['day', 'count']
charts['dow'] = alt.Chart(dow_counts).mark_bar().encode(
    x=alt.X('day:N', sort=dow_order, title='Day of Week'),
    y=alt.Y('count:Q', title='Count'),
    color=alt.condition(
        alt.FieldOneOfPredicate(field='day', oneOf=['Saturday', 'Sunday']),
        alt.value('#e74c3c'), alt.value('#4a90d9')
    ),
    tooltip=['day', 'count']
).properties(title='Errors by Day of Week', width=450, height=220)

# 6. Hour heatmap
hour_dow = df.groupby(['hour', 'day_of_week']).size().reset_index(name='count')
charts['hour_heatmap'] = alt.Chart(hour_dow).mark_rect().encode(
    x=alt.X('hour:O', title='Hour (UTC)'),
    y=alt.Y('day_of_week:N', sort=dow_order, title='Day'),
    color=alt.Color('count:Q', scale=alt.Scale(scheme='viridis'), title='Errors'),
    tooltip=['day_of_week', 'hour', 'count']
).properties(title='Hour x Day Heatmap', width=600, height=180)

# 7. Error patterns
error_patterns = {
    'Invalid Input': r'invalid|not valid|malformed|corrupt',
    'Memory/OOM': r'memory|MemoryError|Cannot allocate|out of memory|OOM',
    'Disk Space': r'No space left|disk full|quota exceeded',
    'Missing Header': r'no.*header|missing header',
    'Connection': r'connection|ConnectionError|network|refused',
    'Process Killed': r'Killed|SIGKILL|signal 9',
    'Permission': r'Permission denied|Access denied',
}
pattern_counts = Counter()
for stderr in df['tool_stderr'].dropna():
    for name, pat in error_patterns.items():
        if re.search(pat, str(stderr), re.IGNORECASE):
            pattern_counts[name] += 1

pattern_df = pd.DataFrame([{'pattern': k, 'count': v} for k, v in pattern_counts.most_common()])
charts['patterns'] = alt.Chart(pattern_df).mark_bar(color='#9b59b6').encode(
    x=alt.X('count:Q', title='Count'),
    y=alt.Y('pattern:N', sort='-x', title='Error Pattern'),
    tooltip=['pattern', 'count']
).properties(title='Error Pattern Categories', width=450, height=220)

# Convert all charts to base64
print("Converting charts to base64...")
chart_images = {}
for name, chart in charts.items():
    chart_images[name] = chart_to_base64(chart)
    print(f"  {name} done")

# Collect stats for tables
top20_tools = df['tool_name'].value_counts().head(20)
top_users = df[df['user_id'].notna()]['user_id'].value_counts().head(10)
exit0_tools = df[df['exit_code'] == 0]['tool_name'].value_counts().head(5)

# Per-tool errors (brief for dashboard)
tool_errors = {}
for tool in top20_tools.index:
    tool_df = df[df['tool_name'] == tool]
    errs = Counter()
    for stderr in tool_df['tool_stderr'].dropna():
        lines = str(stderr).strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and '====' not in line and '____' not in line and len(line) > 10:
                errs[line[:60]] += 1
                break
    tool_errors[tool] = errs.most_common(5)

# Generate individual tool HTML files
print("Generating tool pages...")
Path('tools').mkdir(exist_ok=True)

CSS_STYLE = '''
    :root { --bg: #1a1a2e; --card-bg: #16213e; --text: #eee; --text-muted: #888; --accent: #4a90d9; --border: #0f3460; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; padding: 20px; }
    .container { max-width: 1000px; margin: 0 auto; }
    h1 { color: var(--accent); margin-bottom: 10px; }
    .back { color: var(--accent); text-decoration: none; display: inline-block; margin-bottom: 20px; }
    .back:hover { text-decoration: underline; }
    .stats { display: flex; gap: 20px; margin: 20px 0; flex-wrap: wrap; }
    .stat { background: var(--card-bg); padding: 15px 25px; border-radius: 8px; border: 1px solid var(--border); }
    .stat-value { font-size: 1.5em; font-weight: bold; color: var(--accent); }
    .stat-label { color: var(--text-muted); font-size: 0.85em; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; }
    th, td { padding: 10px; text-align: left; border-bottom: 1px solid var(--border); }
    th { background: rgba(74, 144, 217, 0.2); color: var(--accent); }
    tr:hover { background: rgba(255,255,255,0.05); }
    .error-msg { font-family: monospace; font-size: 0.85em; white-space: pre-wrap; word-break: break-all; background: rgba(0,0,0,0.3); padding: 8px; border-radius: 4px; display: block; margin: 5px 0; }
'''

for tool in top20_tools.index:
    tool_df = df[df['tool_name'] == tool]
    total = len(tool_df)

    # Get ALL unique error messages
    all_errors = Counter()
    full_stderrs = {}
    for stderr in tool_df['tool_stderr'].dropna():
        stderr_str = str(stderr).strip()
        # Get first meaningful line as key
        lines = stderr_str.split('\n')
        key = None
        for line in lines:
            line = line.strip()
            if line and '====' not in line and '____' not in line and '\\' not in line and len(line) > 5:
                key = line[:100]
                break
        if key:
            all_errors[key] += 1
            if key not in full_stderrs:
                full_stderrs[key] = stderr_str[:4000]

    # Exit codes for this tool
    tool_exit_codes = tool_df['exit_code'].value_counts().head(5)

    # Destinations for this tool
    tool_dests = tool_df['destination_id'].value_counts().head(5)

    tool_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{tool} Errors - Galaxy Error Analysis</title>
    <style>{CSS_STYLE}</style>
</head>
<body>
    <div class="container">
        <a href="../index.html" class="back">&larr; Back to Dashboard</a>
        <h1>{tool}</h1>

        <div class="stats">
            <div class="stat">
                <div class="stat-value">{total:,}</div>
                <div class="stat-label">Total Errors</div>
            </div>
            <div class="stat">
                <div class="stat-value">{len(all_errors)}</div>
                <div class="stat-label">Unique Error Types</div>
            </div>
            <div class="stat">
                <div class="stat-value">{tool_df['user_id'].nunique()}</div>
                <div class="stat-label">Affected Users</div>
            </div>
        </div>

        <h2 style="color: var(--accent); margin: 30px 0 15px;">Exit Codes</h2>
        <table>
            <tr><th>Exit Code</th><th>Count</th></tr>
'''
    for ec, cnt in tool_exit_codes.items():
        ec_str = str(int(ec)) if pd.notna(ec) else 'None'
        tool_html += f'            <tr><td>{ec_str}</td><td>{cnt:,}</td></tr>\n'

    tool_html += '''        </table>

        <h2 style="color: var(--accent); margin: 30px 0 15px;">Destinations</h2>
        <table>
            <tr><th>Destination</th><th>Count</th></tr>
'''
    for dest, cnt in tool_dests.items():
        tool_html += f'            <tr><td>{dest}</td><td>{cnt:,}</td></tr>\n'

    tool_html += '''        </table>

        <h2 style="color: var(--accent); margin: 30px 0 15px;">All Unique Error Messages</h2>
        <table>
            <tr><th style="width: 80px;">Count</th><th>Error Message</th></tr>
'''
    for msg, cnt in all_errors.most_common():
        safe_msg = msg.replace('<', '&lt;').replace('>', '&gt;')
        full = full_stderrs.get(msg, '')
        safe_full = full.replace('<', '&lt;').replace('>', '&gt;') if full != msg else ''

        tool_html += f'            <tr><td>{cnt:,}</td><td><span class="error-msg">{safe_msg}</span>'
        if safe_full and len(safe_full) > len(safe_msg) + 20:
            tool_html += f'<details><summary style="color: var(--text-muted); cursor: pointer; margin-top: 5px;">Show full stderr</summary><span class="error-msg" style="margin-top: 10px;">{safe_full}</span></details>'
        tool_html += '</td></tr>\n'

    tool_html += '''        </table>
    </div>
</body>
</html>
'''

    # Sanitize tool name for filename
    safe_tool_name = re.sub(r'[^a-zA-Z0-9_-]', '_', tool)
    with open(f'tools/{safe_tool_name}.html', 'w') as f:
        f.write(tool_html)
    print(f"  {tool} -> tools/{safe_tool_name}.html")

# Spike days
daily_mean = daily['count'].mean()
daily_std = daily['count'].std()
threshold = daily_mean + 2 * daily_std
spikes = daily[daily['count'] > threshold]

# Generate HTML
print("Generating HTML...")

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Galaxy Job Error Analysis Dashboard</title>
    <style>
        :root {{
            --bg: #1a1a2e;
            --card-bg: #16213e;
            --text: #eee;
            --text-muted: #888;
            --accent: #4a90d9;
            --border: #0f3460;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        header {{
            text-align: center;
            padding: 30px 0;
            border-bottom: 1px solid var(--border);
            margin-bottom: 30px;
        }}
        h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .subtitle {{ color: var(--text-muted); font-size: 1.1em; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .stat-card {{
            background: var(--card-bg);
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid var(--border);
        }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: var(--accent); }}
        .stat-label {{ color: var(--text-muted); font-size: 0.9em; }}
        section {{
            background: var(--card-bg);
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 30px;
            border: 1px solid var(--border);
        }}
        h2 {{
            color: var(--accent);
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border);
        }}
        h3 {{ color: var(--text); margin: 20px 0 10px; }}
        .chart {{ text-align: center; margin: 20px 0; }}
        .chart img {{ max-width: 100%; height: auto; border-radius: 8px; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 0.9em;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{ background: rgba(74, 144, 217, 0.2); color: var(--accent); }}
        tr:hover {{ background: rgba(255,255,255,0.05); }}
        code {{
            background: rgba(0,0,0,0.3);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.85em;
            word-break: break-all;
        }}
        .grid-2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }}
        .timestamp {{ color: var(--text-muted); font-size: 0.8em; margin-top: 30px; text-align: center; }}
        @media (max-width: 768px) {{
            .grid-2 {{ grid-template-columns: 1fr; }}
            h1 {{ font-size: 1.8em; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Galaxy Job Error Analysis</h1>
            <p class="subtitle">{df['date'].min()} to {df['date'].max()}</p>
        </header>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{len(df):,}</div>
                <div class="stat-label">Total Errors</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{df['tool_name'].nunique()}</div>
                <div class="stat-label">Unique Tools</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{df['user_id'].nunique():,}</div>
                <div class="stat-label">Unique Users</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{daily['count'].max():,}</div>
                <div class="stat-label">Peak Day Errors</div>
            </div>
        </div>

        <section>
            <h2>1. Tool Failure Analysis</h2>
            <div class="chart">
                <img src="data:image/png;base64,{chart_images['top_tools']}" alt="Top Tools">
            </div>
            <h3>Top 20 Failing Tools</h3>
            <table>
                <tr><th>Tool</th><th>Errors</th><th>Details</th></tr>
'''

for tool, cnt in top20_tools.items():
    safe_tool_name = re.sub(r'[^a-zA-Z0-9_-]', '_', tool)
    html += f'                <tr><td>{tool}</td><td>{cnt:,}</td><td><a href="tools/{safe_tool_name}.html" style="color: var(--accent);">View errors &rarr;</a></td></tr>\n'

html += f'''            </table>
        </section>

        <section>
            <h2>2. Error Classification</h2>
            <div class="grid-2">
                <div class="chart">
                    <img src="data:image/png;base64,{chart_images['exit_codes']}" alt="Exit Codes">
                </div>
                <div class="chart">
                    <img src="data:image/png;base64,{chart_images['patterns']}" alt="Error Patterns">
                </div>
            </div>
        </section>

        <section>
            <h2>2b. Per-Tool Error Breakdown (Top 5 each)</h2>
            <p style="color: var(--text-muted); margin-bottom: 20px;">Click tool name for full error list</p>
'''

for tool in list(top20_tools.index)[:10]:  # Show first 10 in dashboard
    errors = tool_errors.get(tool, [])
    total = top20_tools[tool]
    safe_tool_name = re.sub(r'[^a-zA-Z0-9_-]', '_', tool)
    html += f'''            <h3><a href="tools/{safe_tool_name}.html" style="color: var(--accent); text-decoration: none;">{tool}</a> ({total:,} errors)</h3>
            <table>
                <tr><th>Count</th><th>Error Message</th></tr>
'''
    for msg, cnt in errors:
        safe_msg = msg.replace('<', '&lt;').replace('>', '&gt;')
        html += f'                <tr><td>{cnt:,}</td><td><code>{safe_msg}</code></td></tr>\n'
    html += '            </table>\n'

html += f'''        </section>

        <section>
            <h2>3. Infrastructure Analysis</h2>
            <div class="chart">
                <img src="data:image/png;base64,{chart_images['destinations']}" alt="Destinations">
            </div>
        </section>

        <section>
            <h2>4. Temporal Patterns</h2>
            <div class="chart">
                <img src="data:image/png;base64,{chart_images['daily']}" alt="Daily Trend">
            </div>
            <div class="grid-2">
                <div class="chart">
                    <img src="data:image/png;base64,{chart_images['dow']}" alt="Day of Week">
                </div>
                <div class="chart">
                    <img src="data:image/png;base64,{chart_images['hour_heatmap']}" alt="Hour Heatmap">
                </div>
            </div>
'''

if len(spikes) > 0:
    html += '''            <h3>Spike Days</h3>
            <table>
                <tr><th>Date</th><th>Errors</th></tr>
'''
    for _, row in spikes.iterrows():
        html += f'                <tr><td>{row["date"].strftime("%Y-%m-%d")}</td><td>{row["count"]:,}</td></tr>\n'
    html += '            </table>\n'

html += f'''        </section>

        <section>
            <h2>5. User Impact</h2>
            <h3>Top 10 Users by Error Count</h3>
            <table>
                <tr><th>User ID</th><th>Errors</th></tr>
'''

for uid, cnt in top_users.items():
    html += f'                <tr><td>{int(uid)}</td><td>{cnt:,}</td></tr>\n'

html += f'''            </table>
            <p style="margin-top: 15px; color: var(--text-muted);">Anonymous errors (user_id=None): <strong>{df['user_id'].isna().sum():,}</strong></p>
        </section>

        <section>
            <h2>6. Anomalies</h2>
            <h3>Exit Code 0 Failures</h3>
            <p>{len(df[df['exit_code'] == 0]):,} jobs exited with code 0 but were marked as failed.</p>
            <table>
                <tr><th>Tool</th><th>Count</th></tr>
'''

for tool, cnt in exit0_tools.items():
    html += f'                <tr><td>{tool}</td><td>{cnt:,}</td></tr>\n'

html += f'''            </table>
        </section>

        <p class="timestamp">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
</body>
</html>
'''

with open('index.html', 'w') as f:
    f.write(html)

print(f"Dashboard saved to index.html ({len(html)//1024}KB)")
