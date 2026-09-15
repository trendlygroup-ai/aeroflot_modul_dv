import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta, date
import plotly.graph_objects as go
import sqlite3
import random

st.set_page_config(layout="wide", page_title="AEROFLOT MODUL DV", page_icon="✈️")

DB_FILE = "aeroflot_modul_dv.db"
CORRECT_PASSWORD = "sau2026"

def get_db_connection():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS flights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT NOT NULL,
            flight_num_arr TEXT NOT NULL,
            arrival_time TEXT NOT NULL,
            flight_num_dep TEXT NOT NULL,
            departure_time TEXT NOT NULL,
            destination TEXT NOT NULL,
            aircraft_type TEXT NOT NULL,
            flight_date TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_roster (
            department TEXT NOT NULL,
            shift_name TEXT NOT NULL,
            seniors_count INTEGER,
            juniors_count INTEGER,
            reg_count INTEGER,
            PRIMARY KEY (department, shift_name)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_absent (
            department TEXT NOT NULL,
            target_date TEXT NOT NULL,
            sick_count INTEGER,
            vacation_count INTEGER,
            PRIMARY KEY (department, target_date)
        )
    """)
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM shift_roster")
    if cursor.fetchone() == 0:
        default_roster = [
            ("Хабаровск", "Смена 1", 2, 6, 3),
            ("Хабаровск", "Смена 2", 1, 4, 2),
            ("Владивосток", "Смена 1", 2, 5, 2),
            ("Владивосток", "Смена 2", 2, 3, 2)
        ]
        cursor.executemany("""
            INSERT OR IGNORE INTO shift_roster (department, shift_name, seniors_count, juniors_count, reg_count)
            VALUES (?, ?, ?, ?, ?)
        """, default_roster)
        conn.commit()
    conn.close()

init_db()

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    if st.session_state["password_input"] == CORRECT_PASSWORD:
        st.session_state.authenticated = True
        st.session_state.password_error = False
    else:
        st.session_state.authenticated = False
        st.session_state.password_error = True

if not st.session_state.authenticated:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_l, col_c, col_r = st.columns(3)
    with col_c:
        st.title("🔒 AEROFLOT MODUL DV")
        st.subheader("Система календарно-сменного учета наземных служб")
        st.text_input("Введите секретный код администратора:", type="password", on_change=check_password, key="password_input")
        if st.session_state.get('password_error', False):
            st.error("🛑 Доступ заблокирован. Неверный пароль.")
    st.stop()
with st.sidebar:
    st.header("📅 Параметры планирования")
    selected_dep = st.selectbox("Отделение (Хаб):", ["Хабаровск", "Владивосток", "Южно-Сахалинск", "Якутск", "Петропавловск-Камчатский", "Благовещенск", "Магадан"])
    target_date = st.date_input("Выберите дату суточного плана:", date(2026, 4, 6))
    target_date_str = target_date.strftime("%Y-%m-%d")
    
    st.markdown("---")
    st.header("👥 Управление штатными сменами")
    selected_shift = st.selectbox("Текущая рабочая смена:", ["Смена 1", "Смена 2"])
    
    conn = get_db_connection()
    res_roster = conn.execute("SELECT seniors_count, juniors_count, reg_count FROM shift_roster WHERE department=? AND shift_name=?", (selected_dep, selected_shift)).fetchone()
    conn.close()
    
    init_seniors = res_roster[0] if res_roster else 2
    init_juniors = res_roster[1] if res_roster else 5
    init_reg = res_roster[2] if res_roster else 3
    
    fact_reg = st.number_input("Регистрация на стойках (штат)", min_value=0, max_value=20, value=init_reg)
    fact_ramp_senior = st.number_input("Старшие специалисты (ШФВС)", min_value=0, max_value=20, value=init_seniors)
    fact_ramp_junior = st.number_input("Специалисты (Общий допуск)", min_value=0, max_value=30, value=init_juniors)
    
    if st.button("💾 Сохранить штатный состав смены"):
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO shift_roster (department, shift_name, seniors_count, juniors_count, reg_count)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(department, shift_name) DO UPDATE SET
            seniors_count=excluded.seniors_count, juniors_count=excluded.juniors_count, reg_count=excluded.reg_count
        """, (selected_dep, selected_shift, fact_ramp_senior, fact_ramp_junior, fact_reg))
        conn.commit(); conn.close()
        st.success("Штат смены сохранен!")

    st.markdown("---")
    st.header("🤒 Кадровый учет на дату")
    conn = get_db_connection()
    res_absent = conn.execute("SELECT sick_count, vacation_count FROM daily_absent WHERE department=? AND target_date=?", (selected_dep, target_date_str)).fetchone()
    conn.close()
    
    init_sick = res_absent[0] if res_absent else 0
    init_vac = res_absent[1] if res_absent else 0
    
    sick_leave = st.number_input("Больничные на этот день", min_value=0, max_value=10, value=init_sick)
    vacation = st.number_input("Отпуска на этот день", min_value=0, max_value=10, value=init_vac)
    
    if st.button("💾 Фиксировать невыходы на дату"):
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO daily_absent (department, target_date, sick_count, vacation_count)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(department, target_date) DO UPDATE SET
            sick_count=excluded.sick_count, vacation_count=excluded.vacation_count
        """, (selected_dep, target_date_str, sick_leave, vacation))
        conn.commit(); conn.close()
        st.success("Данные невыходов сохранены!")

    total_absent = sick_leave + vacation
    active_junior = max(0, fact_ramp_junior - total_absent)
    remaining_absent = max(0, total_absent - fact_ramp_junior)
    active_senior = max(0, fact_ramp_senior - remaining_absent)
    fact_ramp_total = active_senior + active_junior

    st.markdown("---")
    st.markdown("### 🚨 Симуляция рисков:")
    enable_emergency = st.checkbox("Посадка самолета на запасной")
    enable_charter = st.checkbox("Добавить чартерный рейс")
    enable_delay = st.checkbox("Моделировать задержку")

st.title(f"✈️ AEROFLOT MODUL — {selected_dep}")
st.subheader(f"📅 Оборотный суточный план на дату: {target_date.strftime('%d.%m.%Y')} ({selected_shift})")
if st.button("🔄 Синхронизировать оборотное расписание с сервера"):
    with st.spinner("Загрузка официального плана полетов ПАО Аэрофлот..."):
        real_turnaround_pool = [
            ("SU-5701", "09:30", "SU-2467", "11:20", "VVO/NER", "Superjet 100"),
            ("SU-6287", "13:25", "SU-6288", "15:50", "SVO", "Boeing 747"),
            ("SU-2468", "16:50", "SU-5702", "18:30", "NER/VVO", "Superjet 100"),
            ("SU-642", "04:45", "SU-643", "06:50", "HKT", "Boeing 77W"),
            ("SU-5703", "06:30", "SU-5707", "07:30", "VVO/UUS", "Superjet 100"),
            ("SU-5806", "08:30", "SU-5807", "10:20", "SVO", "Airbus A332"),
            ("SU-5708", "11:35", "SU-5727", "12:35", "UUS", "Superjet 100"),
            ("SU-1714", "11:45", "SU-1715", "13:45", "SVO", "Boeing 77W"),
            ("SU-1712", "13:45", "SU-1713", "15:45", "SVO", "Airbus A330"),
            ("SU-5755", "16:05", "SU-5756", "17:30", "KJA", "Airbus A319"),
            ("SU-5728", "23:00", "SU-5704", "01:50", "UUS/VVO", "Superjet 100")
        ]
        
        conn = get_db_connection()
        conn.execute("DELETE FROM flights WHERE department=? AND flight_date=?", (selected_dep, target_date_str))
        for r in real_turnaround_pool:
            conn.execute("""
                INSERT INTO flights (department, flight_num_arr, arrival_time, flight_num_dep, departure_time, destination, aircraft_type, flight_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (selected_dep, r[0], r[1], r[2], r[3], r[4], r[5], target_date_str))
        conn.commit(); conn.close()
        st.success("Все оборотные рейсы успешно синхронизированы в СУБД SQLite!"); st.rerun()

with st.expander("➕ Ручное управление оперативным суточным планом хаба (Добавить рейс)"):
    col_add1, col_add2, col_add3, col_add4, col_add5 = st.columns(5)
    with col_add1: manual_arr_num = st.text_input("Рейс Прилет", value="SU-1000")
    with col_add2: manual_arr_time = st.text_input("Время Прил. (ЧЧ:ММ)", value="10:00")
    with col_add3: manual_dep_num = st.text_input("Рейс Вылет", value="SU-1001")
    with col_add4: manual_dep_time = st.text_input("Время Выл. (ЧЧ:ММ)", value="12:00")
    with col_add5: manual_dest = st.text_input("Маршрут", value="SVO")
    
    manual_type = st.selectbox("Тип ВС", ["Airbus A320", "Airbus A321", "Boeing 777", "Superjet 100", "DHC-8"])
        
    if st.button("✈️ Зафиксировать оборотный рейс вручную"):
        if manual_arr_num and manual_dep_num and len(manual_arr_time) == 5 and len(manual_dep_time) == 5:
            conn = get_db_connection()
            conn.execute("""
                INSERT INTO flights (department, flight_num_arr, arrival_time, flight_num_dep, departure_time, destination, aircraft_type, flight_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (selected_dep, manual_arr_num, manual_arr_time, manual_dep_num, manual_dep_time, manual_dest, manual_type, target_date_str))
            conn.commit(); conn.close()
            st.success("Рейс успешно добавлен в суточный план СУБД!"); st.rerun()

conn = get_db_connection()
query = "SELECT flight_num_arr, arrival_time, flight_num_dep, departure_time, destination, aircraft_type FROM flights WHERE department=? AND flight_date=?"
df = pd.read_sql_query(query, conn, params=(selected_dep, target_date_str))
conn.close()

if enable_emergency:
    df = pd.concat([df, pd.DataFrame([{"flight_num_arr": "SU-9912", "arrival_time": "12:00", "flight_num_dep": "SU-9913", "departure_time": "14:30", "destination": "Запасной борт", "aircraft_type": "Boeing 777"}])], ignore_index=True)
if enable_charter:
    df = pd.concat([df, pd.DataFrame([{"flight_num_arr": "SU-CHARTER", "arrival_time": "15:00", "flight_num_dep": "SU-CHARTER_D", "departure_time": "17:15", "destination": "Чартер Пхукет", "aircraft_type": "Airbus A321"}])], ignore_index=True)

calculated_intervals = []
if not df.empty:
    if enable_delay:
        with st.sidebar:
            delayed_flight = st.selectbox("Рейс для моделирования задержки:", df["flight_num_arr"].tolist())
            delay_minutes = st.slider("Время задержки оборота (мин):", 10, 120, 60, 10)

    for idx, row in df.iterrows():
        try:
            t_arr = datetime.strptime(row["arrival_time"], "%H:%M")
            t_dep = datetime.strptime(row["departure_time"], "%H:%M")
            if t_dep < t_arr:
                t_dep += timedelta(days=1)
        except:
            continue
            
        if enable_delay and row["flight_num_arr"] == delayed_flight:
            t_arr += timedelta(minutes=delay_minutes)
            t_dep += timedelta(minutes=delay_minutes)
            lbl_arr = t_arr.strftime("%H:%M") + " (Зад.)"
            lbl_dep = t_dep.strftime("%H:%M") + " (Зад.)"
        else:
            lbl_arr = t_arr.strftime("%H:%M")
            lbl_dep = t_dep.strftime("%H:%M")
            
        r_start = t_dep - timedelta(minutes=120)
        r_end = t_dep - timedelta(minutes=40)
        
        calculated_intervals.append({
            "Рейс Прилет": row["flight_num_arr"], "Время Прил.": lbl_arr,
            "Рейс Вылет": row["flight_num_dep"], "Время Выл.": lbl_dep,
            "Тип ВС": row["aircraft_type"], "Направление": row["destination"],
            "Рег_Старт": r_start.time(), "Рег_Конец": r_end.time(),
            "Перрон_Старт": t_arr, "Перрон_Конец": t_dep
        })
if calculated_intervals:
    intervals_df = pd.DataFrame(calculated_intervals)
    st.markdown("### 📅 Сводная ведомость оборота ВС и окон обслуживания")
    st.dataframe(intervals_df.drop(columns=["Перрон_Старт", "Перрон_Конец"]), use_container_width=True)

    minutes_in_day = 1440
    timeline_reg = np.zeros(minutes_in_day)
    timeline_ramp_total = np.zeros(minutes_in_day)
    timeline_ramp_senior = np.zeros(minutes_in_day)

    for _, row in intervals_df.iterrows():
        m_r_start = row["Рег_Старт"].hour * 60 + row["Рег_Старт"].minute
        m_r_end = row["Рег_Конец"].hour * 60 + row["Рег_Конец"].minute
        
        p_start_dt = row["Перрон_Старт"]
        p_end_dt = row["Перрон_Конец"]
        
        m_p_start = p_start_dt.hour * 60 + p_start_dt.minute
        if p_end_dt.day > p_start_dt.day:
            m_p_end = 1439
        else:
            m_p_end = p_end_dt.hour * 60 + p_end_dt.minute
            
        timeline_reg[m_r_start:m_r_end] = 1
        
        is_widebody = any(t in row["Тип ВС"].upper() for t in ["777", "77W", "747", "330", "332", "350"])
        if is_widebody:
            timeline_ramp_total[m_p_start:m_p_end] += 3   
            timeline_ramp_senior[m_p_start:m_p_end] += 1  
        elif "A321" in row["Тип ВС"].upper() or "A320" in row["Тип ВС"].upper():
            timeline_ramp_total[m_p_start:m_p_end] += 2   
        else:
            timeline_ramp_total[m_p_start:m_p_end] += 1   

    time_labels = [time(h, m).strftime("%H:%M") for h in range(24) for m in range(60)]
    max_ramp = int(np.max(timeline_ramp_total))

    overtime_min = 0; senior_deficit_min = 0
    for m in range(minutes_in_day):
        if timeline_ramp_total[m] > fact_ramp_total: overtime_min += 1
        if timeline_ramp_senior[m] > active_senior: senior_deficit_min += 1

    overtime_h = round(overtime_min / 60, 2)
    
    # Интеллектуальный экономический расчет повышенного ночного тарифа ТК РФ (22:00 - 06:00)
    cost_overtime = 0
    for m in range(minutes_in_day):
        if timeline_ramp_total[m] > fact_ramp_total:
            h = m // 60
            if h >= 22 or h < 6: cost_overtime += int(3000/60)
            else: cost_overtime += int(2500/60)
            
    cost_risk = int(senior_deficit_min * 5000)

    st.markdown("### 📈 Моделирование плотности загрузки перрона (IPG Aero Стенд)")
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Пиковая потребность смены", f"{max_ramp} чел.")
    with col2: st.metric("Активный состав (Факт)", f"{fact_ramp_total} чел.")
    with col3: st.metric("Прогноз бюджета переработок", f"{cost_overtime:,} ₽", f"{overtime_h} ч.")
    with col4: st.metric("Финансовый риск задержек ГТО", f"{cost_risk:,} ₽")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=time_labels, y=timeline_ramp_total, mode='lines', name='Необходимый персонал', line=dict(color='firebrick', width=3)))
    fig.add_trace(go.Scatter(x=time_labels, y=[fact_ramp_total] * minutes_in_day, mode='lines', name='Доступный состав перрона', line=dict(color='rgb(0, 96, 176)', width=2, dash='dash')))
    fig.update_layout(xaxis=dict(title="Суточное время суток (ЧЧ:ММ)", tickmode='array', tickvals=[time(h, 0).strftime("%H:%M") for h in range(0, 24, 2)]), yaxis=dict(title="Сотрудники"), height=360)
    st.plotly_chart(fig, use_container_width=True)

    current_time_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    html_report = f'''<html><head><meta charset="UTF-8"><style>body{{font-family:Arial,sans-serif;margin:30px;}}.block{{background:#e2f0d9;border:2px solid #385723;padding:15px;}}</style></head>
    <body><h2>ПАО АЭРОФЛОТ — ФИНАНСОВО-АНАЛИТИЧЕСКИЙ ОТЧЕТ</h2><p>Хаб: {selected_dep} | Дата: {target_date.strftime("%d.%m.%Y")}</p>
    <div class="block"><h4>💰 Экономические показатели смены:</h4><ul><li>Время дефицита: {overtime_h} ч.</li><li>ФОТ сверхурочных (с учетом ночных): {cost_overtime:,} ₽</li><li>Риск штрафов за задержки ГТО: {cost_risk:,} ₽</li></ul></div>
    </body></html>'''
    st.download_button(label=f"🖨️ Экспортировать суточный аналитический отчет на {target_date.strftime('%d.%m.%Y')}", data=html_report, file_name=f"report_{selected_dep}.html", mime="text/html")
else:
    st.info(f"Суточный план полетов для отделения {selected_dep} пуст. Синхронизируйте данные с сервером кнопкой выше.")


