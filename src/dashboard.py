import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from src.database import SessionLocal
from src.models import Session, Lap
from src.analysis import perform_lap_analysis

# Настройка страницы
st.set_page_config(page_title="F1 2020 Telemetry", layout="wide")
st.title("Анализ телеметрии F1 2020")

@st.cache_resource
def get_db():
    """Кэширование подключения к БД для Streamlit."""
    return SessionLocal()

db = get_db()

# --- САЙДБАР: Фильтры ---
st.sidebar.header("Выбор данных")

# 1. Выбор сессии
sessions = db.query(Session).order_by(Session.date.desc()).all()
if not sessions:
    st.warning("База данных пуста. Запустите сбор телеметрии.")
    st.stop()

session_options = {s.id: f"Сессия {s.id} (Трасса: {s.track_id})" for s in sessions}
selected_session_id = st.sidebar.selectbox("Сессия", options=list(session_options.keys()), format_func=lambda x: session_options[x])

# 2. Выбор кругов
laps = db.query(Lap).filter(Lap.session_id == selected_session_id, Lap.is_valid == True).order_by(Lap.lap_time_ms).all()
if len(laps) < 2:
    st.warning("В выбранной сессии недостаточно валидных кругов для сравнения.")
    st.stop()

lap_options = {l.id: f"Круг {l.lap_number} ({l.lap_time_ms / 1000:.3f} с)" for l in laps}

ref_lap_id = st.sidebar.selectbox("Эталонный круг", options=list(lap_options.keys()), format_func=lambda x: lap_options[x], index=0)
comp_lap_id = st.sidebar.selectbox("Сравниваемый круг", options=list(lap_options.keys()), format_func=lambda x: lap_options[x], index=1)

# --- АНАЛИТИКА ---
if ref_lap_id == comp_lap_id:
    st.error("Выберите разные круги для сравнения.")
    st.stop()

try:
    ref_df, comp_df, insights = perform_lap_analysis(db, ref_lap_id, comp_lap_id)
except ValueError as e:
    st.error(str(e))
    st.stop()

# --- ИНФОРМАЦИОННЫЙ БЛОК (KPI) ---
ref_time = db.query(Lap.lap_time_ms).filter(Lap.id == ref_lap_id).scalar() / 1000
comp_time = db.query(Lap.lap_time_ms).filter(Lap.id == comp_lap_id).scalar() / 1000
delta_time = comp_time - ref_time

col1, col2, col3 = st.columns(3)
col1.metric("Время эталона", f"{ref_time:.3f} с")
col2.metric("Время сравнения", f"{comp_time:.3f} с", delta=f"{delta_time:+.3f} с", delta_color="inverse")

# Вывод автоматических инсайтов
if insights:
    st.subheader("Автоматический анализ ошибок")
    for insight in insights:
        if insight['type'] == 'braking':
            st.warning(insight['message'])
        elif insight['type'] == 'speed':
            st.info(insight['message'])

# --- ПОСТРОЕНИЕ ГРАФИКОВ (PLOTLY) ---
st.subheader("Графики телеметрии")

# Создаем сабплоты с общей осью X (lap_distance)
fig = make_subplots(
    rows=4, cols=1, 
    shared_xaxes=True,
    vertical_spacing=0.05,
    subplot_titles=("Дельта времени (с)", "Скорость (км/ч)", "Педали (Газ / Тормоз)", "Управление (Руль / Передача)"),
    row_heights=[0.15, 0.3, 0.3, 0.25]
)

# 1. Дельта времени
fig.add_trace(go.Scatter(x=comp_df['lap_distance'], y=comp_df['time_delta'], name="Дельта", line=dict(color='red', width=2)), row=1, col=1)

# 2. Скорость
fig.add_trace(go.Scatter(x=ref_df['lap_distance'], y=ref_df['speed'], name="Скорость (Эталон)", line=dict(color='blue')), row=2, col=1)
fig.add_trace(go.Scatter(x=comp_df['lap_distance'], y=comp_df['speed'], name="Скорость (Сравнение)", line=dict(color='orange')), row=2, col=1)

# 3. Педали
fig.add_trace(go.Scatter(x=ref_df['lap_distance'], y=ref_df['throttle'], name="Газ (Эталон)", line=dict(color='blue', dash='solid')), row=3, col=1)
fig.add_trace(go.Scatter(x=comp_df['lap_distance'], y=comp_df['throttle'], name="Газ (Сравнение)", line=dict(color='orange', dash='solid')), row=3, col=1)
fig.add_trace(go.Scatter(x=ref_df['lap_distance'], y=ref_df['brake'], name="Тормоз (Эталон)", line=dict(color='lightblue', dash='dot')), row=3, col=1)
fig.add_trace(go.Scatter(x=comp_df['lap_distance'], y=comp_df['brake'], name="Тормоз (Сравнение)", line=dict(color='navajowhite', dash='dot')), row=3, col=1)

# 4. Руль и передачи
fig.add_trace(go.Scatter(x=ref_df['lap_distance'], y=ref_df['steer'], name="Руль (Эталон)", line=dict(color='blue')), row=4, col=1)
fig.add_trace(go.Scatter(x=comp_df['lap_distance'], y=comp_df['steer'], name="Руль (Сравнение)", line=dict(color='orange')), row=4, col=1)
fig.add_trace(go.Scatter(x=ref_df['lap_distance'], y=ref_df['gear'], name="Передача (Эталон)", line=dict(color='blue', dash='dot')), row=4, col=1)
fig.add_trace(go.Scatter(x=comp_df['lap_distance'], y=comp_df['gear'], name="Передача (Сравнение)", line=dict(color='orange', dash='dot')), row=4, col=1)

# Настройка макета
fig.update_layout(
    height=900,
    hovermode="x unified",
    margin=dict(l=20, r=20, t=40, b=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

fig.update_xaxes(title_text="Дистанция (м)", row=4, col=1)

# Рендеринг в Streamlit
st.plotly_chart(fig, use_container_width=True)