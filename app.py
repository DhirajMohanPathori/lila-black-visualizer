import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from PIL import Image
import base64
from io import BytesIO
import os

st.set_page_config(page_title="LILA BLACK - Map Visualizer", layout="wide")

# ── Map config ───────────────────────────────────────────────
MAP_CONFIG = {
    'AmbroseValley': {'scale': 900,  'origin_x': -370, 'origin_z': -473},
    'GrandRift':     {'scale': 581,  'origin_x': -290, 'origin_z': -290},
    'Lockdown':      {'scale': 1000, 'origin_x': -500, 'origin_z': -500},
}

MINIMAP_FILES = {
    'AmbroseValley': 'minimaps/AmbroseValley_Minimap.png',
    'GrandRift':     'minimaps/GrandRift_Minimap.png',
    'Lockdown':      'minimaps/Lockdown_Minimap.jpg',
}

EVENT_COLORS = {
    'Position':      'rgba(100,149,237,0.6)',
    'BotPosition':   'rgba(169,169,169,0.4)',
    'Kill':          'red',
    'Killed':        'darkred',
    'BotKill':       'orange',
    'BotKilled':     'darkorange',
    'KilledByStorm': 'purple',
    'Loot':          'gold',
}

EVENT_SYMBOLS = {
    'Position':      'circle',
    'BotPosition':   'circle',
    'Kill':          'x',
    'Killed':        'x-open',
    'BotKill':       'triangle-up',
    'BotKilled':     'triangle-down',
    'KilledByStorm': 'star',
    'Loot':          'diamond',
}

def image_to_base64(path):
    img = Image.open(path).convert("RGB")
    img = img.resize((1024, 1024))
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/jpeg;base64,{encoded}"

@st.cache_data
def load_data():
    return pd.read_parquet('all_data.parquet')

@st.cache_data
def load_minimap(map_id):
    return image_to_base64(MINIMAP_FILES[map_id])

df = load_data()

# ── Sidebar ───────────────────────────────────────────────────
st.sidebar.title("🎮 LILA BLACK")
st.sidebar.markdown("### Player Journey Visualizer")

selected_map = st.sidebar.selectbox("Select Map", sorted(df['map_id'].unique()))
dates = sorted(df['date'].unique())
selected_date = st.sidebar.selectbox("Select Date", dates)

filtered = df[(df['map_id'] == selected_map) & (df['date'] == selected_date)]
matches = sorted(filtered['match_id_clean'].unique())
selected_match = st.sidebar.selectbox("Select Match", matches)

view_mode = st.sidebar.radio("View Mode", ["🗺️ Player Journeys", "🔥 Heatmap"])

if view_mode == "🗺️ Player Journeys":
    all_events = sorted(df['event'].unique())
    selected_events = st.sidebar.multiselect("Show Event Types", all_events, default=all_events)
    show_bots = st.sidebar.checkbox("Show Bots", value=True)

# ── Filter match data ─────────────────────────────────────────
match_df = filtered[filtered['match_id_clean'] == selected_match].copy()
match_df = match_df.dropna(subset=['px', 'py'])

# ── Header metrics ────────────────────────────────────────────
st.title(f"LILA BLACK — {selected_map}")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Events", f"{len(match_df):,}")
col2.metric("Human Players", match_df[~match_df['is_bot']]['user_id'].nunique())
col3.metric("Bots", match_df[match_df['is_bot']]['user_id'].nunique())
col4.metric("Date", selected_date.replace('_', ' '))

# ── Load minimap as base64 ────────────────────────────────────
minimap_src = load_minimap(selected_map)

# ── Build figure ──────────────────────────────────────────────
fig = go.Figure()

# Background minimap image
fig.add_layout_image(
    source=minimap_src,
    xref="paper", yref="paper",
    x=0, y=1,
    sizex=1, sizey=1,
    xanchor="left", yanchor="top",
    sizing="stretch",
    opacity=1,
    layer="below"
)

# ── JOURNEY VIEW ─────────────────────────────────────────────
if view_mode == "🗺️ Player Journeys":
    plot_df = match_df[match_df['event'].isin(selected_events)]
    if not show_bots:
        plot_df = plot_df[~plot_df['is_bot']]

    # Movement trails
    position_events = ['Position', 'BotPosition']
    trail_df = plot_df[plot_df['event'].isin(position_events)].sort_values('ts')

    for user_id, udf in trail_df.groupby('user_id'):
        is_bot = udf['is_bot'].iloc[0]
        color = 'rgba(169,169,169,0.35)' if is_bot else 'rgba(100,200,255,0.6)'
        # Normalize to 0-1
        fig.add_trace(go.Scatter(
            x=udf['px'] / 1024,
            y=1 - udf['py'] / 1024,
            mode='lines+markers',
            line=dict(color=color, width=1.5),
            marker=dict(size=3, color=color),
            name=f"{'Bot' if is_bot else 'Player'} {str(user_id)[:8]}",
            hoverinfo='skip',
            showlegend=False
        ))

    # Event markers
    combat_events = [e for e in selected_events if e not in position_events]
    marker_df = plot_df[plot_df['event'].isin(combat_events)]

    for event_type, edf in marker_df.groupby('event'):
        fig.add_trace(go.Scatter(
            x=edf['px'] / 1024,
            y=1 - edf['py'] / 1024,
            mode='markers',
            marker=dict(
                color=EVENT_COLORS.get(event_type, 'white'),
                symbol=EVENT_SYMBOLS.get(event_type, 'circle'),
                size=12,
                line=dict(width=1.5, color='white')
            ),
            name=event_type,
            hovertemplate=f"<b>{event_type}</b><br>Player: %{{text}}<extra></extra>",
            text=edf['user_id'].astype(str).str[:8]
        ))

# ── HEATMAP VIEW ──────────────────────────────────────────────
elif view_mode == "🔥 Heatmap":
    heatmap_type = st.sidebar.selectbox(
        "Heatmap Type",
        ["All Movement", "Kills Only", "Deaths Only", "Loot Only", "Storm Deaths"]
    )
    heatmap_filter = {
        "All Movement": ['Position', 'BotPosition'],
        "Kills Only":   ['Kill', 'BotKill'],
        "Deaths Only":  ['Killed', 'BotKilled'],
        "Loot Only":    ['Loot'],
        "Storm Deaths": ['KilledByStorm'],
    }
    heat_df = match_df[match_df['event'].isin(heatmap_filter[heatmap_type])]

    if len(heat_df) > 0:
        fig.add_trace(go.Histogram2dContour(
            x=heat_df['px'] / 1024,
            y=1 - heat_df['py'] / 1024,
            colorscale='Hot',
            reversescale=True,
            opacity=0.65,
            showscale=True,
            contours=dict(showlines=False),
            name=heatmap_type
        ))
    else:
        st.warning(f"No '{heatmap_type}' events in this match.")

# ── Figure layout ─────────────────────────────────────────────
fig.update_layout(
    xaxis=dict(range=[0, 1], showgrid=False, zeroline=False,
               showticklabels=False, fixedrange=True),
    yaxis=dict(range=[0, 1], showgrid=False, zeroline=False,
               showticklabels=False, scaleanchor='x', fixedrange=True),
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='#0e1117',
    margin=dict(l=0, r=0, t=0, b=0),
    height=700,
    legend=dict(
        bgcolor='rgba(0,0,0,0.6)',
        font=dict(color='white', size=11),
        x=1.01
    )
)

st.plotly_chart(fig, use_container_width=True)

# ── Match stats ───────────────────────────────────────────────
with st.expander("📊 Match Event Breakdown"):
    summary = match_df.groupby(['event', 'is_bot']).size().reset_index(name='count')
    summary['player_type'] = summary['is_bot'].map({True: 'Bot', False: 'Human'})
    st.dataframe(summary[['event', 'player_type', 'count']], use_container_width=True)
