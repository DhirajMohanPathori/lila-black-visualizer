import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from PIL import Image
import base64
from io import BytesIO
import os
import time

st.set_page_config(page_title="LILA BLACK - Map Visualizer", layout="wide", page_icon="🎮")

# ── Custom CSS ────────────────────────────────────────────────
st.markdown("""
<style>
    /* Dark theme overrides */
    .stApp { background-color: #0e1117; }
    section[data-testid="stSidebar"] { background-color: #1a1a2e; border-right: 1px solid #2d2d4e; }
    section[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
    
    /* Title */
    .main-title {
        font-size: 2rem; font-weight: 800; color: #ffffff;
        text-transform: uppercase; letter-spacing: 3px;
        border-bottom: 2px solid #e63946; padding-bottom: 8px;
        margin-bottom: 16px;
    }
    .subtitle { color: #7f8c8d; font-size: 0.85rem; letter-spacing: 2px; margin-top: -12px; }

    /* Metric cards */
    .metric-card {
        background: #1a1a2e; border: 1px solid #2d2d4e;
        border-radius: 8px; padding: 12px 16px;
        text-align: center;
    }
    .metric-label { color: #7f8c8d; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; }
    .metric-value { color: #ffffff; font-size: 1.6rem; font-weight: 700; }
    .metric-sub { color: #e63946; font-size: 0.75rem; }

    /* Legend */
    .legend-item { display: flex; align-items: center; gap: 8px; margin: 4px 0; font-size: 0.8rem; color: #ccc; }
    .legend-dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }

    /* Playback controls */
    .playback-bar {
        background: #1a1a2e; border: 1px solid #2d2d4e;
        border-radius: 8px; padding: 12px 16px; margin-top: 8px;
    }
    
    /* Selectbox and widgets */
    .stSelectbox > div > div { background-color: #16213e !important; border-color: #2d2d4e !important; }
    .stRadio > div { gap: 8px; }
    
    /* Expander */
    .streamlit-expanderHeader { background-color: #1a1a2e !important; color: #e0e0e0 !important; }
    
    /* Hide streamlit branding */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

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
    'Position':      '#4fc3f7',
    'BotPosition':   '#78909c',
    'Kill':          '#ef5350',
    'Killed':        '#b71c1c',
    'BotKill':       '#ffa726',
    'BotKilled':     '#e65100',
    'KilledByStorm': '#ab47bc',
    'Loot':          '#ffd54f',
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

EVENT_ICONS = {
    'Kill': '💀', 'Killed': '☠️', 'BotKill': '🤖',
    'BotKilled': '🤖', 'KilledByStorm': '🌪️', 'Loot': '📦'
}

def world_to_norm(x, z, map_id):
    """Convert world coords to normalized 0-1 coords for plotting."""
    cfg = MAP_CONFIG[map_id]
    u = (x - cfg['origin_x']) / cfg['scale']
    v = (z - cfg['origin_z']) / cfg['scale']
    # Clamp to 0-1
    u = max(0, min(1, u))
    v = max(0, min(1, v))
    return u, 1 - v  # flip Y axis

@st.cache_data
def load_data():
    df = pd.read_parquet('all_data.parquet')
    return df

@st.cache_data
def load_minimap(map_id):
    path = MINIMAP_FILES[map_id]
    img = Image.open(path).convert("RGB")
    img = img.resize((1024, 1024))
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=90)
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/jpeg;base64,{encoded}"

def make_figure(minimap_src):
    fig = go.Figure()
    fig.add_layout_image(
        source=minimap_src,
        xref="paper", yref="paper",
        x=0, y=1, sizex=1, sizey=1,
        xanchor="left", yanchor="top",
        sizing="stretch", opacity=1, layer="below"
    )
    fig.update_layout(
        xaxis=dict(range=[0,1], showgrid=False, zeroline=False, showticklabels=False, fixedrange=True),
        yaxis=dict(range=[0,1], showgrid=False, zeroline=False, showticklabels=False, scaleanchor='x', fixedrange=True),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='#0e1117',
        margin=dict(l=0, r=0, t=0, b=0),
        height=680,
        legend=dict(
            bgcolor='rgba(15,15,30,0.85)',
            bordercolor='#2d2d4e',
            borderwidth=1,
            font=dict(color='white', size=11),
            x=1.01
        ),
        showlegend=True
    )
    return fig

# ── Load data ─────────────────────────────────────────────────
df = load_data()

# ── Apply coordinate conversion ───────────────────────────────
# Recompute norm_x, norm_y using verified formula
if 'norm_x' not in df.columns:
    def apply_norm(row):
        nx, ny = world_to_norm(row['x'], row['z'], row['map_id'])
        return pd.Series([nx, ny])
    df[['norm_x', 'norm_y']] = df.apply(apply_norm, axis=1)

# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎮 LILA BLACK")
    st.markdown("### Player Journey Visualizer")
    st.markdown("---")

    selected_map = st.selectbox("🗺️ Map", sorted(df['map_id'].unique()))
    dates = sorted(df['date'].unique())
    selected_date = st.selectbox("📅 Date", dates)

    filtered = df[(df['map_id'] == selected_map) & (df['date'] == selected_date)]
    matches = sorted(filtered['match_id_clean'].unique())
    selected_match = st.selectbox("🎯 Match ID", matches,
        format_func=lambda x: x[:18] + "...")

    st.markdown("---")
    view_mode = st.radio("View Mode", ["🗺️ Journey", "🔥 Heatmap", "📊 Aggregate"])

    st.markdown("---")

    if view_mode == "🗺️ Journey":
        st.markdown("**Event Filters**")
        all_events = sorted(df['event'].unique())
        selected_events = st.multiselect("Show Events", all_events, default=all_events)
        show_humans = st.checkbox("Show Humans", value=True)
        show_bots = st.checkbox("Show Bots", value=True)
        show_trails = st.checkbox("Show Movement Trails", value=True)

    elif view_mode == "🔥 Heatmap":
        heatmap_type = st.selectbox("Heatmap Layer", [
            "All Movement", "Kills Only", "Deaths Only",
            "Loot Only", "Storm Deaths", "Human Movement Only"
        ])
        heatmap_opacity = st.slider("Opacity", 0.3, 1.0, 0.65)

    elif view_mode == "📊 Aggregate":
        agg_event = st.selectbox("Event Type", [
            "Kill", "Killed", "KilledByStorm", "Loot", "BotKill", "BotKilled"
        ])

# ── Filter match ──────────────────────────────────────────────
match_df = filtered[filtered['match_id_clean'] == selected_match].copy()
match_df = match_df.dropna(subset=['x', 'z'])

# Apply coordinate conversion
coords = match_df.apply(lambda r: pd.Series(world_to_norm(r['x'], r['z'], r['map_id'])), axis=1)
match_df['norm_x'] = coords[0]
match_df['norm_y'] = coords[1]
match_df = match_df.sort_values('ts')

# ── Header ────────────────────────────────────────────────────
st.markdown(f'<div class="main-title">LILA BLACK</div>', unsafe_allow_html=True)
st.markdown(f'<div class="subtitle">MAP: {selected_map.upper()}  |  {selected_date.replace("_"," ").upper()}</div>', unsafe_allow_html=True)

# Metrics
humans = match_df[~match_df['is_bot']]['user_id'].nunique()
bots = match_df[match_df['is_bot']]['user_id'].nunique()
kills = len(match_df[match_df['event'].isin(['Kill', 'BotKill'])])
loots = len(match_df[match_df['event'] == 'Loot'])
storm = len(match_df[match_df['event'] == 'KilledByStorm'])

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Total Events</div><div class="metric-value">{len(match_df):,}</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Human Players</div><div class="metric-value">{humans}</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Bots</div><div class="metric-value">{bots}</div></div>', unsafe_allow_html=True)
with c4:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Kills</div><div class="metric-value">{kills}</div><div class="metric-sub">💀</div></div>', unsafe_allow_html=True)
with c5:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Storm Deaths</div><div class="metric-value">{storm}</div><div class="metric-sub">🌪️</div></div>', unsafe_allow_html=True)

st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)

# ── Load minimap ──────────────────────────────────────────────
minimap_src = load_minimap(selected_map)
fig = make_figure(minimap_src)

# ── JOURNEY VIEW ─────────────────────────────────────────────
if view_mode == "🗺️ Journey":

    plot_df = match_df.copy()
    if selected_events:
        plot_df = plot_df[plot_df['event'].isin(selected_events)]
    if not show_humans:
        plot_df = plot_df[plot_df['is_bot']]
    if not show_bots:
        plot_df = plot_df[~plot_df['is_bot']]

    # Timeline slider
    ts_vals = match_df['ts'].astype('int64') // 1_000_000
    ts_min, ts_max = int(ts_vals.min()), int(ts_vals.max())
    duration = ts_max - ts_min

    st.markdown('<div class="playback-bar">', unsafe_allow_html=True)
    col_play, col_slider = st.columns([1, 8])
    with col_play:
        playing = st.button("▶ Play")
    with col_slider:
        timeline_pct = st.slider("Match Timeline", 0, 100, 100,
            format="%d%%", label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

    # Filter by timeline
    ts_cutoff = ts_min + int((timeline_pct / 100) * duration)
    plot_df = plot_df[ts_vals[plot_df.index] <= ts_cutoff]

    # Auto-play logic
    if playing:
        placeholder = st.empty()
        for pct in range(0, 101, 2):
            ts_cut = ts_min + int((pct / 100) * duration)
            frame_df = plot_df[ts_vals[plot_df.index] <= ts_cut]
            frame_fig = make_figure(minimap_src)

            # Trails
            if show_trails:
                for uid, udf in frame_df[frame_df['event'].isin(['Position','BotPosition'])].groupby('user_id'):
                    is_bot = udf['is_bot'].iloc[0]
                    color = 'rgba(120,144,156,0.4)' if is_bot else 'rgba(79,195,247,0.7)'
                    frame_fig.add_trace(go.Scatter(
                        x=udf['norm_x'], y=udf['norm_y'],
                        mode='lines', line=dict(color=color, width=1.5),
                        showlegend=False, hoverinfo='skip'
                    ))

            placeholder.plotly_chart(frame_fig, use_container_width=True)
            time.sleep(0.05)

    # Draw trails
    if show_trails:
        pos_events = ['Position', 'BotPosition']
        trail_df = plot_df[plot_df['event'].isin(pos_events)]

        for uid, udf in trail_df.groupby('user_id'):
            is_bot = udf['is_bot'].iloc[0]
            if (is_bot and not show_bots) or (not is_bot and not show_humans):
                continue
            color = 'rgba(120,144,156,0.4)' if is_bot else 'rgba(79,195,247,0.7)'
            label = f"{'🤖 Bot' if is_bot else '👤 Player'} {str(uid)[:8]}"
            fig.add_trace(go.Scatter(
                x=udf['norm_x'], y=udf['norm_y'],
                mode='lines+markers',
                line=dict(color=color, width=1.5),
                marker=dict(size=2, color=color),
                name=label,
                hoverinfo='skip',
                showlegend=True
            ))

    # Draw event markers
    combat = [e for e in (selected_events or []) if e not in ['Position', 'BotPosition']]
    marker_df = plot_df[plot_df['event'].isin(combat)]

    for event_type, edf in marker_df.groupby('event'):
        icon = EVENT_ICONS.get(event_type, '')
        fig.add_trace(go.Scatter(
            x=edf['norm_x'], y=edf['norm_y'],
            mode='markers',
            marker=dict(
                color=EVENT_COLORS.get(event_type, 'white'),
                symbol=EVENT_SYMBOLS.get(event_type, 'circle'),
                size=14,
                line=dict(width=1.5, color='white'),
                opacity=0.95
            ),
            name=f"{icon} {event_type}",
            hovertemplate=(
                f"<b>{icon} {event_type}</b><br>"
                "Player: %{text}<br>"
                "<extra></extra>"
            ),
            text=edf['user_id'].astype(str).str[:12]
        ))

# ── HEATMAP VIEW ──────────────────────────────────────────────
elif view_mode == "🔥 Heatmap":

    heatmap_filter = {
        "All Movement":        ['Position', 'BotPosition'],
        "Human Movement Only": ['Position'],
        "Kills Only":          ['Kill', 'BotKill'],
        "Deaths Only":         ['Killed', 'BotKilled'],
        "Loot Only":           ['Loot'],
        "Storm Deaths":        ['KilledByStorm'],
    }

    heat_df = match_df[match_df['event'].isin(heatmap_filter[heatmap_type])]

    if len(heat_df) >= 3:
        fig.add_trace(go.Histogram2dContour(
            x=heat_df['norm_x'],
            y=heat_df['norm_y'],
            colorscale='Hot',
            reversescale=True,
            opacity=heatmap_opacity,
            showscale=True,
            contours=dict(showlines=False, coloring='fill'),
            ncontours=20,
            name=heatmap_type,
            hovertemplate="Density: %{z}<extra></extra>"
        ))

        # Also show event dots on top
        fig.add_trace(go.Scatter(
            x=heat_df['norm_x'], y=heat_df['norm_y'],
            mode='markers',
            marker=dict(
                color=EVENT_COLORS.get(heatmap_filter[heatmap_type][0], 'white'),
                size=4, opacity=0.3
            ),
            name="Events",
            hoverinfo='skip',
            showlegend=False
        ))
    else:
        st.warning(f"⚠️ Not enough data for '{heatmap_type}' heatmap in this match. Try a different match or event type.")

# ── AGGREGATE VIEW ────────────────────────────────────────────
elif view_mode == "📊 Aggregate":
    st.info(f"Showing ALL '{agg_event}' events across every match on {selected_map} on {selected_date}")

    agg_df = filtered[filtered['event'] == agg_event].copy()
    coords2 = agg_df.apply(lambda r: pd.Series(world_to_norm(r['x'], r['z'], r['map_id'])), axis=1)
    agg_df['norm_x'] = coords2[0]
    agg_df['norm_y'] = coords2[1]

    if len(agg_df) >= 3:
        fig.add_trace(go.Histogram2dContour(
            x=agg_df['norm_x'], y=agg_df['norm_y'],
            colorscale='Plasma',
            reversescale=False,
            opacity=0.7,
            showscale=True,
            contours=dict(showlines=False, coloring='fill'),
            ncontours=25,
            name=f"All {agg_event}s"
        ))
        st.caption(f"Total {agg_event} events across all matches: **{len(agg_df):,}**")
    else:
        st.warning(f"Not enough '{agg_event}' events on this map/date.")

# ── Render chart ──────────────────────────────────────────────
st.plotly_chart(fig, use_container_width=True)

# ── Match breakdown ───────────────────────────────────────────
with st.expander("📊 Match Event Breakdown"):
    col_a, col_b = st.columns(2)
    with col_a:
        summary = match_df.groupby(['event']).size().reset_index(name='count').sort_values('count', ascending=False)
        st.dataframe(summary, use_container_width=True, hide_index=True)
    with col_b:
        human_df = match_df[~match_df['is_bot']]
        bot_df = match_df[match_df['is_bot']]
        st.markdown(f"**Human events:** {len(human_df):,}")
        st.markdown(f"**Bot events:** {len(bot_df):,}")
        st.markdown(f"**Unique matches today:** {len(matches)}")
        st.markdown(f"**Map:** {selected_map}")