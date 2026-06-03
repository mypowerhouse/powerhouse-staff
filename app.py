"""
Powerhouse Staff — Client Behavior
Acceso restringido con contraseña para el equipo interno.
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ── Config ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Powerhouse · Comportamiento Clientes",
    page_icon="🏋️",
    layout="wide",
)

DB_PATH = Path(__file__).parent / "data" / "fitness_ops.db"

COLORS = {"RGS": "#E63946", "Armida": "#457B9D", "neutral": "#A8DADC"}

STATUS_LABELS = {
    "attended":    "Asistió",
    "cancelled":   "Canceló a tiempo",
    "late_cancel": "Cancelación tardía",
    "no_show":     "No-show",
}

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

    st.image("https://i.imgur.com/placeholder.png", width=120)  # swap for PH logo URL
    st.title("Powerhouse — Acceso Staff")
    st.text_input("Contraseña", type="password", key="pwd", on_change=verify)
    st.stop()

check_password()

# ── DB helpers ──────────────────────────────────────────────────────────────────
# Using cursor directly — compatible with pandas 2.x + Python 3.12/3.14
def _q(sql, params=()):
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    try:
        cursor = conn.execute(sql, params)
        cols = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        return pd.DataFrame(rows, columns=cols)
    finally:
        conn.close()

def get_available_months():
    df = _q("SELECT DISTINCT strftime('%Y-%m', class_date) as m FROM attendance ORDER BY m DESC")
    return df["m"].tolist() if not df.empty else []

def get_client_summary(email, month_from, month_to, studio_id=None):
    studio_filter = "AND studio_id = :sid" if studio_id else ""
    sql = f"""
        SELECT
            member_email,
            member_name,
            strftime('%Y-%m', class_date) AS month,
            COUNT(*) AS total_bookings,
            SUM(CASE WHEN status='late_cancel' THEN 1 ELSE 0 END) AS late_cancels,
            SUM(CASE WHEN status='no_show'     THEN 1 ELSE 0 END) AS no_shows,
            SUM(CASE WHEN status='attended'    THEN 1 ELSE 0 END) AS attended
        FROM attendance
        WHERE member_email = :email
          AND strftime('%Y-%m', class_date) BETWEEN :mf AND :mt
          {studio_filter}
        GROUP BY member_email, month
        ORDER BY month DESC
    """
    params = {"email": email.lower().strip(), "mf": month_from, "mt": month_to}
    if studio_id:
        params["sid"] = studio_id
    return _q(sql, params)

def get_all_clients_month(month_from, month_to, studio_id=None):
    studio_filter = "AND studio_id = :sid" if studio_id else ""
    sql = f"""
        SELECT
            member_email,
            MAX(member_name) AS member_name,
            SUM(CASE WHEN status='late_cancel' THEN 1 ELSE 0 END) AS late_cancels,
            SUM(CASE WHEN status='no_show'     THEN 1 ELSE 0 END) AS no_shows,
            COUNT(*) AS total_bookings,
            SUM(CASE WHEN status='attended'    THEN 1 ELSE 0 END) AS attended
        FROM attendance
        WHERE strftime('%Y-%m', class_date) BETWEEN :mf AND :mt
          {studio_filter}
          AND member_email IS NOT NULL AND member_email != ''
        GROUP BY member_email
        ORDER BY (late_cancels + no_shows) DESC
    """
    params = {"mf": month_from, "mt": month_to}
    if studio_id:
        params["sid"] = studio_id
    return _q(sql, params)

def get_detail(email, month_from, month_to, studio_id=None):
    studio_filter = "AND studio_id = :sid" if studio_id else ""
    sql = f"""
        SELECT class_date, class_name, studio_id, status
        FROM attendance
        WHERE member_email = :email
          AND strftime('%Y-%m', class_date) BETWEEN :mf AND :mt
          {studio_filter}
        ORDER BY class_date DESC
    """
    params = {"email": email.lower().strip(), "mf": month_from, "mt": month_to}
    if studio_id:
        params["sid"] = studio_id
    return _q(sql, params)

# ── UI ──────────────────────────────────────────────────────────────────────────
st.title("🏋️ Powerhouse — Comportamiento de Clientes")
st.caption("Cancelaciones tardías y no-shows por cliente")

available_months = get_available_months()
if not available_months:
    st.warning("Sin datos de asistencia cargados.")
    st.stop()

# Filters
col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
with col1:
    email_input = st.text_input("Buscar cliente por email", placeholder="cliente@correo.com")
with col2:
    month_from = st.selectbox("Desde", options=sorted(available_months), index=len(available_months)-1)
with col3:
    month_to = st.selectbox("Hasta", options=sorted(available_months), index=0)
with col4:
    studio_opt = st.selectbox("Estudio", ["Todos", "RGS", "Armida"])

studio_id = None
if studio_opt != "Todos":
    df_sid = _q("SELECT id FROM studios WHERE name=?", (studio_opt,))
    studio_id = int(df_sid["id"].iloc[0]) if not df_sid.empty else None

# ── Client search ───────────────────────────────────────────────────────────────
if email_input.strip():
    email = email_input.strip().lower()
    df_hist = get_client_summary(email, month_from, month_to, studio_id)

    if df_hist.empty:
        st.info(f"Sin registros para **{email}** en el período seleccionado.")
    else:
        name = df_hist["member_name"].iloc[0] if "member_name" in df_hist.columns else ""
        total_lc = int(df_hist["late_cancels"].sum())
        total_ns = int(df_hist["no_shows"].sum())
        total_bk = int(df_hist["total_bookings"].sum())
        total_at = int(df_hist["attended"].sum())

        st.subheader(f"{'👤 ' + name if name else email}")

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Total reservas", total_bk)
        k2.metric("Asistencias", total_at)
        k3.metric("Cancelaciones tardías", total_lc,
                  delta=f"{total_lc/total_bk*100:.1f}%" if total_bk else None,
                  delta_color="inverse")
        k4.metric("No-shows", total_ns,
                  delta=f"{total_ns/total_bk*100:.1f}%" if total_bk else None,
                  delta_color="inverse")
        k5.metric("Tasa problema", f"{(total_lc+total_ns)/total_bk*100:.1f}%" if total_bk else "—")

        st.divider()
        st.subheader("Historial mensual")
        df_hist["% LC"] = (df_hist["late_cancels"] / df_hist["total_bookings"] * 100).round(1)
        df_hist["% NS"] = (df_hist["no_shows"] / df_hist["total_bookings"] * 100).round(1)
        st.dataframe(df_hist.rename(columns={
            "month": "Mes", "total_bookings": "Reservas",
            "attended": "Asistencias", "late_cancels": "Tard.", "no_shows": "NS"
        })[["Mes","Reservas","Asistencias","Tard.","% LC","NS","% NS"]],
        use_container_width=True, hide_index=True)

        st.subheader("Detalle de clases")
        df_det = get_detail(email, month_from, month_to, studio_id)
        if not df_det.empty:
            df_det["status_label"] = df_det["status"].map(STATUS_LABELS).fillna(df_det["status"])
            df_det["studio_name"] = df_det["studio_id"].map({1:"RGS",2:"Armida"})
            st.dataframe(df_det[["class_date","class_name","studio_name","status_label"]].rename(columns={
                "class_date":"Fecha","class_name":"Clase","studio_name":"Estudio","status_label":"Estado"
            }), use_container_width=True, hide_index=True)

# ── Browse mode ─────────────────────────────────────────────────────────────────
else:
    st.subheader("Clientes con más incidencias en el período")
    df_all = get_all_clients_month(month_from, month_to, studio_id)
    if df_all.empty:
        st.info("Sin datos para el período seleccionado.")
    else:
        df_all["% problema"] = ((df_all["late_cancels"] + df_all["no_shows"]) / df_all["total_bookings"] * 100).round(1)
        df_all = df_all[df_all["total_bookings"] >= 2]  # filter noise
        st.dataframe(df_all.rename(columns={
            "member_email":"Email","member_name":"Nombre",
            "total_bookings":"Reservas","attended":"Asistencias",
            "late_cancels":"Tard.","no_shows":"NS"
        })[["Email","Nombre","Reservas","Asistencias","Tard.","NS","% problema"]],
        use_container_width=True, hide_index=True, height=500)

        fig = px.bar(
            df_all.head(15),
            x="member_email", y=["late_cancels","no_shows"],
            labels={"value":"Cantidad","member_email":"Cliente","variable":"Tipo"},
            color_discrete_map={"late_cancels":"#E63946","no_shows":"#457B9D"},
            title="Top 15 clientes con más incidencias"
        )
        fig.update_layout(xaxis_tickangle=-35, legend_title="")
        st.plotly_chart(fig, use_container_width=True)
