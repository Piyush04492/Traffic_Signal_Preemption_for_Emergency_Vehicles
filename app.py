import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from simulation_engine import run_simulation

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="V2X Emergency Preemption — 5G vs 4G vs Baseline",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Light system-matching CSS ────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp { background: #f5f7fa; }
[data-testid="stSidebar"] { background:#ffffff; border-right:1px solid #dde3ec; }

/* Section headers */
.sec { font-size:15px; font-weight:700; color:#1e293b;
       border-left:4px solid #2563eb; padding-left:10px; margin:24px 0 8px; }

/* KPI cards */
.kpi { background:#fff; border:1px solid #dde3ec; border-radius:10px;
       padding:16px 18px; text-align:center;
       box-shadow:0 1px 4px rgba(0,0,0,.06); }
.kpi-label { font-size:11px; color:#64748b; text-transform:uppercase;
             letter-spacing:.08em; margin-bottom:5px; }
.kpi-value { font-size:28px; font-weight:700; color:#0f172a; }
.kpi-unit  { font-size:12px; color:#94a3b8; margin-left:2px; }

/* Console */
.console { background:#f1f5f9; border:1px solid #cbd5e1;
           border-left:4px solid #2563eb; border-radius:8px;
           padding:12px 14px; font-family:monospace; font-size:12px;
           color:#334155; max-height:220px; overflow-y:auto; line-height:1.6; }

/* Run button */
div.stButton > button { width:100%; font-weight:600; border-radius:8px;
    background:#2563eb; color:#fff; border:none; padding:10px; font-size:14px; }
div.stButton > button:hover { background:#1d4ed8; }

/* Chart card wrapper */
.chart-card { background:#fff; border:1px solid #dde3ec; border-radius:12px;
              padding:16px; margin-bottom:16px;
              box-shadow:0 1px 4px rgba(0,0,0,.05); }
.chart-title { font-size:13px; font-weight:700; color:#1e293b; margin-bottom:6px; }
</style>
""", unsafe_allow_html=True)

# ─── Colour map ───────────────────────────────────────────────────────────────
CLR = {"Baseline": "#ef4444", "4G": "#f59e0b", "5G URLLC": "#22c55e"}
PT  = "plotly_white"   # plotly template (matches light system theme)

def _chart_layout(title="", **kw):
    """Consistent Plotly layout with visible border-style styling."""
    return dict(
        title=dict(text=title, font=dict(size=13, color="#1e293b"), x=0),
        template=PT,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#f8fafc",
        margin=dict(l=50, r=20, t=45, b=40),
        font=dict(family="Inter", size=11, color="#475569"),
        **kw,
    )

def kpi(label, value, unit=""):
    return (f'<div class="kpi"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}'
            f'<span class="kpi-unit">{unit}</span></div></div>')

# ─── Session state for stored results ────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = {}   # mode → latest result dict

# ─── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.title("⚙️ Simulation Settings")

mode_opts = ["5G URLLC", "4G LTE", "Baseline (No Preemption)", "Batch — Run All 3"]
sel_mode  = st.sidebar.selectbox("Preemption Mode", mode_opts)

st.sidebar.markdown("---")
st.sidebar.subheader("🚗 Traffic Density")
density = st.sidebar.slider("Civilian Traffic Density", 0.1, 0.8, 0.3, 0.05,
    help="0.1=sparse  0.8=very dense mixed traffic (cars+buses+trucks+motos)")

st.sidebar.subheader("📡 5G URLLC — Direct PC5 Sidelink")
lat_5g = st.sidebar.slider("5G Latency (ms)", 1, 3, 2, 1,
    help="Direct Device-to-Infrastructure PC5 V2I communication: 1–3 ms latency.")

st.sidebar.subheader("📶 4G LTE — Cloud-Routed V2I")
lat_4g = st.sidebar.slider("4G Latency (ms)", 20, 60, 50, 5,
    help="Uplink to eNodeB + core network backhaul + cloud V2X processing + downlink command: 20–60 ms.")
loss_4g = st.sidebar.slider("Packet Loss Rate (%)", 0, 20, 10, 1,
    help="Packet drops cause RLC retransmissions adding 30-80ms delay.")

st.sidebar.markdown("---")
launch_gui = st.sidebar.checkbox("🖥️ Launch SUMO GUI window", value=True,
    help="Opens visual SUMO window. Uncheck = headless / faster.")

# If there is already history, let user clear it
if st.session_state.history:
    if st.sidebar.button("🗑️ Clear stored results"):
        st.session_state.history = {}
        st.rerun()

# ─── Page header ─────────────────────────────────────────────────────────────
st.title("🚨 V2X Emergency Signal Preemption Simulator")
st.markdown(
    "Comparing **5G URLLC** (direct sidelink) · **4G LTE** (cloud V2I) · **Baseline** (no preemption)  \n"
    "Powered by **SUMO** traffic simulation + **TraCI** Python control"
)
st.markdown("---")

# ─── Mode mapping ─────────────────────────────────────────────────────────────
_MAP = {
    "5G URLLC":                 "5G URLLC",
    "4G LTE":                   "4G",
    "Baseline (No Preemption)": "Baseline",
}

run_btn = st.button("▶  Run Simulation Now")

# ─── Run handler ─────────────────────────────────────────────────────────────
if run_btn:
    batch    = (sel_mode == "Batch — Run All 3")
    to_run   = ["Baseline", "4G", "5G URLLC"] if batch else [_MAP[sel_mode]]
    prog     = st.progress(0, text="Initialising simulation…")

    for i, m in enumerate(to_run):
        prog.progress(i / len(to_run), text=f"Running {m} simulation…")
        with st.spinner(f"Running **{m}** mode via {'SUMO-GUI' if launch_gui else 'Headless'}…"):
            try:
                r = run_simulation(
                    mode=m,
                    civilian_density=density,
                    lat_4g_ms=lat_4g,
                    loss_4g_pct=loss_4g,
                    lat_5g_ms=lat_5g,
                    headless=(not launch_gui),
                )
                st.session_state.history[m] = r
            except Exception as e:
                st.error(f"**{m}** failed: {e}")
        prog.progress((i + 1) / len(to_run))

    prog.empty()
    st.success(f"✅ Simulation complete — results stored for comparison.")


# ─── Show results if we have any ─────────────────────────────────────────────
hist = st.session_state.history
if not hist:
    st.info("👆 Configure settings in the sidebar and press **Run Simulation Now** to start.")
    st.stop()

stored_modes = list(hist.keys())   # e.g. ["Baseline", "4G"] after 2 runs


# ══════════════════════════════════════════════════════════════════════════════
# LATEST RUN PANEL (always show the most-recently completed run)
# ══════════════════════════════════════════════════════════════════════════════
last_mode = stored_modes[-1]
res = hist[last_mode]

badge_colour = {"5G URLLC": "#22c55e", "4G": "#f59e0b", "Baseline": "#ef4444"}.get(last_mode, "#3b82f6")
st.markdown(
    f'<div class="sec">Latest Run — '
    f'<span style="background:{badge_colour}22;color:{badge_colour};'
    f'border-radius:6px;padding:2px 10px;font-size:13px">{last_mode}</span></div>',
    unsafe_allow_html=True
)

# Derive "time lost vs best" from stored history
best_time = min((v["ev_travel_time"] for v in hist.values()), default=None)
time_lost  = round(res["ev_travel_time"] - best_time, 2) if best_time is not None else None

c1, c2, c3, c4, c5 = st.columns(5)
with c1: st.markdown(kpi("🚨 EV Travel Time",
                          f"{res['ev_travel_time']:.2f}", "s"), unsafe_allow_html=True)
with c2: st.markdown(kpi("🛑 Stopped Delay",
                          f"{res['ev_delay']:.2f}", "s"), unsafe_allow_html=True)
with c3: st.markdown(kpi("🚗 Avg EV Speed",
                          f"{res['ev_avg_speed']:.1f}", "km/h"), unsafe_allow_html=True)
with c4:
    avg_lat = (res["latency_c1_ms"] + res["latency_c2_ms"]) / 2 if last_mode != "Baseline" else None
    if avg_lat is not None:
        lat_val_str = f"{avg_lat:.1f}" if avg_lat < 10 else f"{avg_lat:.0f}"
    else:
        lat_val_str = "N/A"
    st.markdown(kpi("📡 V2I Latency", lat_val_str, "ms" if avg_lat is not None else ""), unsafe_allow_html=True)
with c5:
    lost_str = f"+{time_lost:.1f}" if time_lost and time_lost > 0 else "0.0"
    st.markdown(kpi("⏱️ Time Lost vs Best", lost_str, "s"), unsafe_allow_html=True)
st.markdown("")

if last_mode == "4G" and "5G URLLC" in hist:
    st.info(
        f"📊 **Why is 4G travel time {time_lost:.1f}s longer than 5G?**  "
        "Direct 5G sidelink V2I range reaches 100m, allowing the ambulance to preempt the light early and pass at full speed. "
        "Due to cellular routing and localization constraints, 4G has a reliable preemption range of only 12m. "
        "This late trigger forces the ambulance to decelerate and lose momentum before the light turns green."
    )

# Speed profile + latency dist for latest run
col_a, col_b = st.columns(2)
with col_a:
    df_ts = pd.DataFrame(res["time_series"])
    if not df_ts.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_ts["time"], y=df_ts["ev_speed"],
            fill="tozeroy", mode="lines",
            line=dict(color=CLR.get(last_mode, "#3b82f6"), width=2),
            name=last_mode,
        ))
        fig.update_layout(**_chart_layout(
            title=f"Ambulance Speed Profile ({last_mode})",
            xaxis_title="Simulation Time (s)",
            yaxis_title="Speed (km/h)",
        ))
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

with col_b:
    samples = res["latency_samples"]
    if samples:
        fig_h = go.Figure(go.Histogram(
            x=samples, nbinsx=20,
            marker_color=CLR.get(last_mode, "#3b82f6"),
            marker_line=dict(color="white", width=0.5),
            opacity=0.85,
        ))
        fig_h.add_vline(x=np.mean(samples), line_dash="dash",
                        annotation_text=f"μ = {np.mean(samples):.1f} ms",
                        line_color="#475569")
        fig_h.update_layout(**_chart_layout(
            title=f"Network Latency Distribution ({last_mode})",
            xaxis_title="Latency (ms)",
            yaxis_title="Sample Count",
        ))
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.plotly_chart(fig_h, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("No latency data — Baseline mode has no V2I communication.")

# Event log
st.markdown('<div class="sec">Simulation Event Log</div>', unsafe_allow_html=True)
log_html = "\n".join(res["logs"])
st.markdown(f'<div class="console">{log_html}</div>', unsafe_allow_html=True)

# Download for latest
df_dl = pd.DataFrame(res["time_series"])
st.download_button("📥 Download Speed Profile CSV", df_dl.to_csv(index=False),
                   file_name=f"v2x_{last_mode.replace(' ', '_')}_speed.csv",
                   mime="text/csv")


# ══════════════════════════════════════════════════════════════════════════════
# COMPARISON PANEL (shown when ≥ 2 different modes are stored)
# ══════════════════════════════════════════════════════════════════════════════
if len(stored_modes) >= 2:
    st.markdown("---")
    st.markdown(f'<div class="sec">📊 Stored Results Comparison ({", ".join(stored_modes)})</div>',
                unsafe_allow_html=True)

    # Summary table matching the attached screenshot columns
    rows = []
    for m in stored_modes:
        r = hist[m]
        rows.append({
            "Mode":               m,
            "Travel Time (s)":    r["ev_travel_time"],
            "Stopped Delay (s)":  r["ev_delay"],
            "Avg Speed (km/h)":   r["ev_avg_speed"],
            "Civilian Delay (s)": r["civilian_delay"],
            "Latency C1 (ms)":    f"{r['latency_c1_ms']:.1f}" if m != "Baseline" else "—",
            "Latency C2 (ms)":    f"{r['latency_c2_ms']:.1f}" if m != "Baseline" else "—",
        })
    df_tbl = pd.DataFrame(rows).set_index("Mode")
    st.dataframe(df_tbl, use_container_width=True)
    st.caption(
        "**Travel Time** = total simulation time for ambulance to traverse full corridor.  "
        "**Time Lost vs Best** = extra seconds vs the fastest mode (5G URLLC).  "
        "4G's travel time is longer because the ambulance decelerates/nearly-stops and "
        "must reaccelerate — even brief momentum loss compounds across two intersections."
    )
    st.markdown("")

    col1, col2 = st.columns(2)

    # 1 — Travel time
    with col1:
        fig1 = go.Figure([go.Bar(
            x=stored_modes,
            y=[hist[m]["ev_travel_time"] for m in stored_modes],
            marker_color=[CLR.get(m, "#94a3b8") for m in stored_modes],
            marker_line=dict(color="#1e293b", width=1),
            text=[f"{hist[m]['ev_travel_time']:.2f} s" for m in stored_modes],
            textposition="outside",
        )])
        fig1.update_layout(**_chart_layout(
            title="Emergency Vehicle Travel Time (lower = better)",
            yaxis_title="seconds", showlegend=False,
        ))
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.plotly_chart(fig1, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # 2 — Stopped delay
    with col2:
        fig2 = go.Figure([go.Bar(
            x=stored_modes,
            y=[hist[m]["ev_delay"] for m in stored_modes],
            marker_color=[CLR.get(m, "#94a3b8") for m in stored_modes],
            marker_line=dict(color="#1e293b", width=1),
            text=[f"{hist[m]['ev_delay']:.2f} s" for m in stored_modes],
            textposition="outside",
        )])
        fig2.update_layout(**_chart_layout(
            title="EV Stopped Delay at Intersections (lower = better)",
            yaxis_title="seconds", showlegend=False,
        ))
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    col3, col4 = st.columns(2)

    # 3 — Civilian delay
    with col3:
        fig3 = go.Figure([go.Bar(
            x=stored_modes,
            y=[hist[m]["civilian_delay"] for m in stored_modes],
            marker_color=[CLR.get(m, "#94a3b8") for m in stored_modes],
            marker_line=dict(color="#1e293b", width=1),
            text=[f"{hist[m]['civilian_delay']:.0f} s" for m in stored_modes],
            textposition="outside",
        )])
        fig3.update_layout(**_chart_layout(
            title="Civilian Traffic Delay — Preemption Trade-off",
            yaxis_title="cumulative seconds", showlegend=False,
        ))
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.plotly_chart(fig3, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # 4 — Overlaid speed profiles
    with col4:
        fig4 = go.Figure()
        for m in stored_modes:
            df_m = pd.DataFrame(hist[m]["time_series"])
            if not df_m.empty:
                fig4.add_trace(go.Scatter(
                    x=df_m["time"], y=df_m["ev_speed"],
                    name=m, mode="lines",
                    line=dict(color=CLR.get(m, "#94a3b8"), width=2.5),
                ))
        fig4.update_layout(**_chart_layout(
            title="Ambulance Speed Profiles — Overlaid Comparison",
            xaxis_title="Time (s)", yaxis_title="Speed (km/h)",
            legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1, xanchor="right"),
        ))
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.plotly_chart(fig4, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # 5 — Latency distribution overlay
    modes_with_lat = [m for m in stored_modes if hist[m]["latency_samples"]]
    if modes_with_lat:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        fig5 = go.Figure()
        for m in modes_with_lat:
            s = hist[m]["latency_samples"]
            fig5.add_trace(go.Histogram(
                x=s, name=m, nbinsx=25,
                marker_color=CLR.get(m, "#94a3b8"),
                marker_line=dict(color="white", width=0.5),
                opacity=0.75,
            ))
            fig5.add_vline(x=np.mean(s), line_dash="dash",
                           line_color=CLR.get(m, "#94a3b8"),
                           annotation_text=f"{m}: μ={np.mean(s):.1f} ms",
                           annotation_font_color=CLR.get(m, "#333"),
                           annotation_position="top right")
        fig5.update_layout(**_chart_layout(
            title="Network Latency Distribution — V2I Round-Trip Samples",
            xaxis_title="Latency (ms)", yaxis_title="Sample Count",
            barmode="overlay",
            legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1, xanchor="right"),
        ))
        st.plotly_chart(fig5, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # 6 — Per-intersection latency bar
    modes_with_exec = [m for m in stored_modes
                       if hist[m]["latency_c1_ms"] > 0 or hist[m]["latency_c2_ms"] > 0]
    if modes_with_exec:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        fig6 = go.Figure()
        for m in modes_with_exec:
            fig6.add_trace(go.Bar(
                name=m,
                x=["Intersection C1", "Intersection C2"],
                y=[hist[m]["latency_c1_ms"], hist[m]["latency_c2_ms"]],
                marker_color=CLR.get(m, "#94a3b8"),
                marker_line=dict(color="#1e293b", width=1),
                text=[f"{hist[m]['latency_c1_ms']:.0f} ms",
                      f"{hist[m]['latency_c2_ms']:.0f} ms"],
                textposition="outside",
            ))
        fig6.update_layout(**_chart_layout(
            title="Measured V2I Preemption Latency by Intersection",
            yaxis_title="Latency (ms)",
            barmode="group",
            legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1, xanchor="right"),
        ))
        st.plotly_chart(fig6, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # CSV export
    export = []
    for m in stored_modes:
        r = hist[m]
        s = r["latency_samples"]
        export.append({
            "Mode":            m,
            "TravelTime_s":    r["ev_travel_time"],
            "StoppedDelay_s":  r["ev_delay"],
            "AvgSpeed_kmh":    r["ev_avg_speed"],
            "CivDelay_s":      r["civilian_delay"],
            "LatC1_ms":        r["latency_c1_ms"],
            "LatC2_ms":        r["latency_c2_ms"],
            "LatMean_ms":      round(np.mean(s), 2) if s else 0,
            "LatStd_ms":       round(np.std(s),  2) if s else 0,
        })
    st.download_button(
        "📥 Download Full Comparison Report (CSV)",
        pd.DataFrame(export).to_csv(index=False),
        file_name="v2x_comparison_report.csv",
        mime="text/csv",
    )
