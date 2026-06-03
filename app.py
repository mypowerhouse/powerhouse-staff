"""
Powerhouse Staff — Comportamiento de Clientes
Acceso restringido con contraseña para el equipo interno.
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ── Config ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Powerhouse · Clientes",
    page_icon="🏋️",
    layout="wide",
)

DB_PATH = Path(__file__).parent / "data" / "fitness_ops.db"

# ── Password gate ───────────────────────────────────────────────────────────────
def check_password():
    def verify():
        if st.session_state["pwd"] == st.secrets["password"]:
            st.session_state["auth"] = True
        else:
            st.session_state["auth"] = False
            st.error("Contraseña incorrecta.")

    if st.session_state.get("auth"):
        return True

    st.markdown("## 🏋️ Powerhouse — Acceso Staff")
    st.text_input("Contraseña", type="password", key="pwd", on_change=verify)
    st.stop()

check_password()

# ── DB helper ───────────────────────────────────────────────────────────────────
def _q(sql, params=()):
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    try:
        cursor = conn.execute(sql, params)
        cols = [d[0] for d in cursor.description]
        return pd.DataFrame(cursor.fetchall(), columns=cols)
    finally:
        conn.close()

# ── Queries ─────────────────────────────────────────────────────────────────────
def get_months():
    df = _q("SELECT DISTINCT month FROM client_monthly_stats ORDER BY month DESC")
    return df["month"].tolist()

def get_client_history(email):
    """Monthly history for a specific client — aggregated across CSV sources."""
    return _q("""
        SELECT
            month,
            MAX(member_name)    AS nombre,
            MAX(membership)     AS membresia,
            SUM(late_cancels)   AS cancelaciones_tardias,
            SUM(no_shows)       AS no_shows
        FROM client_monthly_stats
        WHERE LOWER(member_email) = LOWER(?)
        GROUP BY month
        ORDER BY month DESC
    """, (email.strip(),))

def get_all_clients(month_from, month_to):
    """All clients in period, sorted by worst behavior."""
    return _q("""
        SELECT
            member_email                        AS email,
            MAX(member_name)                    AS nombre,
            SUM(late_cancels)                   AS cancelaciones_tardias,
            SUM(no_shows)                       AS no_shows,
            SUM(late_cancels) + SUM(no_shows)   AS total_incidencias
        FROM client_monthly_stats
        WHERE month BETWEEN ? AND ?
          AND member_email IS NOT NULL
          AND member_email != ''
        GROUP BY member_email
        HAVING total_incidencias > 0
        ORDER BY total_incidencias DESC
    """, (month_from, month_to))

def search_email(term):
    """Autocomplete — find emails that contain the search term."""
    return _q("""
        SELECT DISTINCT member_email, MAX(member_name) AS nombre
        FROM client_monthly_stats
        WHERE LOWER(member_email) LIKE LOWER(?)
           OR LOWER(member_name)  LIKE LOWER(?)
        GROUP BY member_email
        LIMIT 10
    """, (f"%{term}%", f"%{term}%"))

# ── UI ──────────────────────────────────────────────────────────────────────────
st.title("🏋️ Powerhouse — Comportamiento de Clientes")
st.caption("Cancelaciones tardías y no-shows · Datos Ene–May 2026")

months = get_months()
if not months:
    st.error("Sin datos en la base de datos.")
    st.stop()

# ── Filters ─────────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    email_input = st.text_input(
        "🔍 Buscar cliente por email o nombre",
        placeholder="ejemplo@correo.com o nombre del cliente",
    )
with col2:
    month_from = st.selectbox("Desde", sorted(months), index=len(months) - 1)
with col3:
    month_to = st.selectbox("Hasta", sorted(months), index=0)

if month_from > month_to:
    st.warning("'Desde' no puede ser mayor que 'Hasta'. Ajusta el rango.")
    st.stop()

st.divider()

# ── CLIENT DETAIL VIEW ──────────────────────────────────────────────────────────
if email_input.strip():
    term = email_input.strip()

    # Try exact match first, then fuzzy
    exact = "@" in term
    if exact:
        df_hist = get_client_history(term)
    else:
        # Search by name / partial email
        matches = search_email(term)
        if matches.empty:
            st.info(f"No se encontró ningún cliente con '{term}'.")
            st.stop()
        if len(matches) > 1:
            st.write("**Clientes encontrados — selecciona uno:**")
            selected = st.radio(
                "Clientes",
                matches["email"].tolist(),
                format_func=lambda e: f"{matches.loc[matches['email']==e,'nombre'].values[0]}  ({e})",
                label_visibility="collapsed",
            )
            term = selected
        else:
            term = matches["email"].iloc[0]
        df_hist = get_client_history(term)

    # Filter to selected range
    df_range = df_hist[
        (df_hist["month"] >= month_from) & (df_hist["month"] <= month_to)
    ]

    if df_hist.empty:
        st.info(f"Sin registros para **{term}**.")
        st.stop()

    nombre = df_hist["nombre"].iloc[0] or term
    total_lc = int(df_range["cancelaciones_tardias"].sum())
    total_ns = int(df_range["no_shows"].sum())
    total_inc = total_lc + total_ns

    # Header
    st.subheader(f"👤 {nombre}")
    st.caption(f"`{term}`  ·  {df_hist['membresia'].iloc[0]}")

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Período analizado", f"{month_from} → {month_to}")
    k2.metric("Cancelaciones tardías", total_lc,
              delta="⚠️ Alto" if total_lc >= 5 else None, delta_color="inverse")
    k3.metric("No-shows", total_ns,
              delta="⚠️ Alto" if total_ns >= 5 else None, delta_color="inverse")
    k4.metric("Total incidencias", total_inc,
              delta="🔴 Crítico" if total_inc >= 10 else ("🟡 Revisar" if total_inc >= 5 else "🟢 OK"),
              delta_color="inverse" if total_inc >= 5 else "normal")

    st.divider()

    # Monthly breakdown
    st.subheader("Historial mensual")
    df_display = df_hist.copy()
    df_display["Mes"] = df_display["month"]
    df_display["Membresía"] = df_display["membresia"]
    df_display["Canc. tardías"] = df_display["cancelaciones_tardias"]
    df_display["No-shows"] = df_display["no_shows"]
    df_display["Total"] = df_display["cancelaciones_tardias"] + df_display["no_shows"]

    def color_row(row):
        total = row["Total"]
        if total >= 5:
            return ["background-color: #3d1a1a"] * len(row)
        elif total >= 3:
            return ["background-color: #3d2e1a"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df_display[["Mes", "Membresía", "Canc. tardías", "No-shows", "Total"]]
        .style.apply(color_row, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    # Chart
    if len(df_hist) > 1:
        fig = px.bar(
            df_hist,
            x="month", y=["cancelaciones_tardias", "no_shows"],
            labels={"value": "Cantidad", "month": "Mes", "variable": "Tipo"},
            color_discrete_map={
                "cancelaciones_tardias": "#E63946",
                "no_shows": "#457B9D",
            },
            title=f"Incidencias por mes — {nombre}",
        )
        fig.update_layout(
            legend_title="",
            plot_bgcolor="#1a1a1a",
            paper_bgcolor="#1a1a1a",
            font_color="white",
        )
        fig.for_each_trace(lambda t: t.update(
            name="Canc. tardías" if t.name == "cancelaciones_tardias" else "No-shows"
        ))
        st.plotly_chart(fig, use_container_width=True)

# ── BROWSE MODE ─────────────────────────────────────────────────────────────────
else:
    st.subheader(f"📋 Clientes con incidencias · {month_from} → {month_to}")
    df_all = get_all_clients(month_from, month_to)

    if df_all.empty:
        st.info("Sin incidencias en el período seleccionado.")
        st.stop()

    # Summary KPIs
    k1, k2, k3 = st.columns(3)
    k1.metric("Clientes con incidencias", len(df_all))
    k2.metric("Total cancelaciones tardías", int(df_all["cancelaciones_tardias"].sum()))
    k3.metric("Total no-shows", int(df_all["no_shows"].sum()))

    st.divider()

    # Top 15 chart
    fig = px.bar(
        df_all.head(15),
        x="nombre",
        y=["cancelaciones_tardias", "no_shows"],
        labels={"value": "Cantidad", "nombre": "Cliente", "variable": "Tipo"},
        color_discrete_map={
            "cancelaciones_tardias": "#E63946",
            "no_shows": "#457B9D",
        },
        title="Top 15 clientes con más incidencias",
    )
    fig.update_layout(
        xaxis_tickangle=-35,
        legend_title="",
        plot_bgcolor="#1a1a1a",
        paper_bgcolor="#1a1a1a",
        font_color="white",
    )
    fig.for_each_trace(lambda t: t.update(
        name="Canc. tardías" if t.name == "cancelaciones_tardias" else "No-shows"
    ))
    st.plotly_chart(fig, use_container_width=True)

    # Full table
    st.subheader("Lista completa")
    st.dataframe(
        df_all.rename(columns={
            "email": "Email",
            "nombre": "Nombre",
            "cancelaciones_tardias": "Canc. tardías",
            "no_shows": "No-shows",
            "total_incidencias": "Total",
        }),
        use_container_width=True,
        hide_index=True,
        height=450,
    )

    # Download button
    csv = df_all.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Descargar lista (CSV)",
        csv,
        f"incidencias_{month_from}_{month_to}.csv",
        "text/csv",
    )
