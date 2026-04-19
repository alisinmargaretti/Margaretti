import streamlit as st
import pandas as pd
import numpy as np
import calendar
import json
import time
from datetime import datetime
from pathlib import Path

st.set_page_config(page_title="Пицца-Про: Учет производства", layout="wide")

DB_FILE = Path("production_data.json")
BACKUP_DIR = Path("backups")
BACKUP_DIR.mkdir(exist_ok=True)

# --- СИСТЕМА ХРАНЕНИЯ ДАННЫХ ---
def load_data():
    if DB_FILE.exists():
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if "history" in data:
                    for k in data["history"]:
                        data["history"][k] = pd.DataFrame(data["history"][k])
                return data
            except:
                return {"history": {}, "month_data": {}}
    return {"history": {}, "month_data": {}}

def save_data():
    data_to_save = {
        "history": {k: v.to_dict() for k, v in st.session_state.history.items()},
        "month_data": st.session_state.month_data
    }
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False)
    
    last_backup = st.session_state.get("last_backup", 0)
    if time.time() - last_backup > 3600:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"backup_{ts}.json"
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False)
        st.session_state.last_backup = time.time()

if 'initialized' not in st.session_state:
    saved = load_data()
    st.session_state.history = saved["history"]
    st.session_state.month_data = saved["month_data"]
    st.session_state.initialized = True

MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}

def get_month_data(m_key):
    if m_key not in st.session_state.month_data:
        st.session_state.month_data[m_key] = {
            "staff_bakers": [{"Имя": f"Пекарь {i+1}", "Ставка": 3500.0, "Начало": 1, "Тип": "Черная", "Оф_часть": 0.0, "Vacation": []} for i in range(6)],
            "staff_assemblers": [{"Имя": f"Сборщик {i+1}", "Ставка": 3000.0, "Начало": 1, "Тип": "Черная", "Оф_часть": 0.0, "Vacation": []} for i in range(4)],
            "staff_office": [
                {"Имя": "Руководитель производства", "Оклад": 80000.0, "Тип": "Черная", "Оф_часть": 0.0, "Vacation": []},
                {"Имя": "Менеджер", "Оклад": 50000.0, "Тип": "Черная", "Оф_часть": 0.0, "Vacation": []},
                {"Имя": "Бухгалтер", "Оклад": 45000.0, "Тип": "Черная", "Оф_часть": 0.0, "Vacation": []},
                {"Имя": "Директор по развитию", "Оклад": 100000.0, "Тип": "Черная", "Оф_часть": 0.0, "Vacation": []}
            ],
            "plans": {"pb": 30000, "pp": 10000, "mode": "1 смена (12ч)"}
        }
    
    # ПРОВЕРКА ЦЕЛОСТНОСТИ ДАННЫХ
    m_data = st.session_state.month_data[m_key]
    for category in ["staff_bakers", "staff_assemblers", "staff_office"]:
        if category in m_data:
            for i in range(len(m_data[category])):
                if "Тип" not in m_data[category][i]: m_data[category][i]["Тип"] = "Черная"
                if "Оф_часть" not in m_data[category][i]: m_data[category][i]["Оф_часть"] = 0.0
                if "Vacation" not in m_data[category][i]: m_data[category][i]["Vacation"] = []
                # Миграция старых дат в список (если были)
                if not isinstance(m_data[category][i]["Vacation"], list):
                    m_data[category][i]["Vacation"] = []
    
    if "staff_office" not in m_data:
        m_data["staff_office"] = [
            {"Имя": "Руководитель производства", "Оклад": 80000.0},
            {"Имя": "Менеджер", "Оклад": 50000.0},
            {"Имя": "Бухгалтер", "Оклад": 45000.0},
            {"Имя": "Директор по развитию", "Оклад": 100000.0}
        ]
    return m_data

# --- БОКОВАЯ ПАНЕЛЬ ---
now = datetime.now()
sel_month_name = st.sidebar.selectbox("📅 Месяц", list(MONTHS_RU.values()), index=now.month-1)
sel_month_idx = [k for k, v in MONTHS_RU.items() if v == sel_month_name][0]
sel_year = st.sidebar.number_input("Год", value=now.year)
m_key = f"{sel_month_idx}_{sel_year}"
m_store = get_month_data(m_key)
num_days = calendar.monthrange(sel_year, sel_month_idx)[1]

def add_baker(): m_store["staff_bakers"].append({"Имя": "Новый пекарь", "Ставка": 3500.0, "Начало": 1, "Тип": "Черная", "Оф_часть": 0.0}); save_data()
def add_assembler(): m_store["staff_assemblers"].append({"Имя": "Новый сборщик", "Ставка": 3000.0, "Начало": 1, "Тип": "Черная", "Оф_часть": 0.0}); save_data()
def remove_baker(index): m_store["staff_bakers"].pop(index); save_data(); st.rerun()
def remove_assembler(index): m_store["staff_assemblers"].pop(index); save_data(); st.rerun()
def add_office(): m_store["staff_office"].append({"Имя": "Новый сотрудник", "Оклад": 50000.0, "Тип": "Черная", "Оф_часть": 0.0}); save_data()
def remove_office(index): m_store["staff_office"].pop(index); save_data(); st.rerun()

def generate_auto_schedule(plan_bases_total, plan_pizza, b_perf, a_perf, shifts_day, n_days, bakers, assemblers):
    b_shifts_needed = int(np.ceil(plan_bases_total / b_perf / shifts_day)) if b_perf > 0 else 0
    if b_shifts_needed > 0:
        common_b_days = np.linspace(0, n_days - 1, min(b_shifts_needed, n_days), dtype=int)
    else:
        common_b_days = []

    schedule = {}
    for emp in bakers:
        s_idx = emp.get("Начало", 1) - 1
        vaca = emp.get("Vacation", [])
        row = [0.0] * n_days
        for d_idx in common_b_days:
            if d_idx >= s_idx and (d_idx + 1) not in vaca:
                row[d_idx] = 12.0
        schedule[emp["Имя"]] = row

    p_shifts_total = int(np.ceil(plan_pizza / a_perf)) if a_perf > 0 else 0
    num_a = len(assemblers)
    shifts_per_assm = int(np.ceil(p_shifts_total / num_a / shifts_day)) if num_a > 0 else 0
    
    for emp in assemblers:
        s = emp.get("Начало", 1)
        vaca = emp.get("Vacation", [])
        avail_indices = [idx for idx in range(s-1, n_days) if (idx + 1) not in vaca]
        
        row = [0.0] * n_days
        needed = shifts_per_assm * shifts_day
        # Простой алгоритм распределения по доступным дням
        for count, idx in enumerate(avail_indices):
            if count < needed:
                row[idx] = 12.0
        schedule[emp["Имя"]] = row
    return pd.DataFrame(schedule, index=range(1, n_days+1)).T

with st.sidebar.expander("🏗️ Настройки цеха", expanded=False):
    b_limit = st.number_input("Макс. основ/смену", value=1800)
    p_limit = st.number_input("Пицц на сборщика", value=250)
    a_shok = st.number_input("Количество сборщиков", value=4)

st.sidebar.markdown("---")
st.sidebar.subheader("👨‍🍳 Цех выпечки")
for i, b in enumerate(m_store["staff_bakers"]):
    with st.sidebar.expander(f"👤 {b['Имя']}", expanded=False):
        m_store["staff_bakers"][i]["Имя"] = st.text_input("Имя", b["Имя"], key=f"v_bn_{i}_{m_key}")
        c1, c2 = st.columns(2)
        m_store["staff_bakers"][i]["Ставка"] = c1.number_input("Ставка (за смену)", value=float(b["Ставка"]), key=f"v_bs_{i}_{m_key}")
        m_store["staff_bakers"][i]["Начало"] = c2.number_input("Дата выхода (число)", 1, num_days, int(b.get("Начало", 1)), key=f"v_bd_s_{i}_{m_key}")
        
        pay_type = st.selectbox("Тип оплаты", ["Белая", "Черная", "Серая"], index=["Белая", "Черная", "Серая"].index(b.get("Тип", "Черная")), key=f"bt_{i}_{m_key}")
        m_store["staff_bakers"][i]["Тип"] = pay_type
        if pay_type == "Серая":
            m_store["staff_bakers"][i]["Оф_часть"] = st.number_input("Офиц. часть (на карту)", value=float(b.get("Оф_часть", 0.0)), key=f"bo_{i}_{m_key}")
        
        # Календарь отсутствий через выбор диапазона
        st.write("📅 Период отсутствия")
        v_dates = st.date_input(
            "Выберите диапазон",
            value=[],
            key=f"bv_date_{i}_{m_key}",
            min_value=datetime(sel_year, sel_month_idx, 1),
            max_value=datetime(sel_year, sel_month_idx, num_days)
        )
        if isinstance(v_dates, (list, tuple)) and len(v_dates) == 2:
            d_range = pd.date_range(v_dates[0], v_dates[1]).day.tolist()
            if m_store["staff_bakers"][i]["Vacation"] != d_range:
                m_store["staff_bakers"][i]["Vacation"] = d_range
                save_data()
        elif isinstance(v_dates, (list, tuple)) and len(v_dates) == 1:
             m_store["staff_bakers"][i]["Vacation"] = [v_dates[0].day]
             save_data()
        
        if st.button("Удалить сотрудника", key=f"bd_del_{i}_{m_key}"): remove_baker(i)
st.sidebar.button("➕ Добавить пекаря", on_click=add_baker)

st.sidebar.divider()
st.sidebar.subheader("🛠️ Цех сборки")
for i, a in enumerate(m_store["staff_assemblers"]):
    with st.sidebar.expander(f"👤 {a['Имя']}", expanded=False):
        m_store["staff_assemblers"][i]["Имя"] = st.text_input("Имя", a["Имя"], key=f"v_an_{i}_{m_key}")
        c1, c2 = st.columns(2)
        m_store["staff_assemblers"][i]["Ставка"] = c1.number_input("Ставка (за смену)", value=float(a["Ставка"]), key=f"v_as_{i}_{m_key}")
        m_store["staff_assemblers"][i]["Начало"] = c2.number_input("Дата выхода (число)", 1, num_days, int(a.get("Начало", 1)), key=f"v_ad_s_{i}_{m_key}")
        
        pay_type = st.selectbox("Тип оплаты", ["Белая", "Черная", "Серая"], index=["Белая", "Черная", "Серая"].index(a.get("Тип", "Черная")), key=f"at_{i}_{m_key}")
        m_store["staff_assemblers"][i]["Тип"] = pay_type
        if pay_type == "Серая":
            m_store["staff_assemblers"][i]["Оф_часть"] = st.number_input("Офиц. часть (на карту)", value=float(a.get("Оф_часть", 0.0)), key=f"ao_{i}_{m_key}")
        
        st.write("📅 Период отсутствия")
        v_dates_a = st.date_input(
            "Выберите диапазон",
            value=[],
            key=f"av_date_{i}_{m_key}",
            min_value=datetime(sel_year, sel_month_idx, 1),
            max_value=datetime(sel_year, sel_month_idx, num_days)
        )
        if isinstance(v_dates_a, (list, tuple)) and len(v_dates_a) == 2:
            d_range = pd.date_range(v_dates_a[0], v_dates_a[1]).day.tolist()
            if m_store["staff_assemblers"][i]["Vacation"] != d_range:
                m_store["staff_assemblers"][i]["Vacation"] = d_range
                save_data()
        elif isinstance(v_dates_a, (list, tuple)) and len(v_dates_a) == 1:
            m_store["staff_assemblers"][i]["Vacation"] = [v_dates_a[0].day]
            save_data()

        if st.button("Удалить сотрудника", key=f"ad_del_{i}_{m_key}"): remove_assembler(i)
st.sidebar.button("➕ Добавить сборщика", on_click=add_assembler)

st.sidebar.divider()
st.sidebar.subheader("🏢 Офис")
for i, o in enumerate(m_store.get("staff_office", [])):
    with st.sidebar.expander(f"🏢 {o['Имя']}", expanded=False):
        m_store["staff_office"][i]["Имя"] = st.text_input("Имя", o["Имя"], key=f"v_on_{i}_{m_key}")
        m_store["staff_office"][i]["Оклад"] = st.number_input("Оклад (за месяц)", value=float(o["Оклад"]), key=f"v_os_{i}_{m_key}")
        
        pay_type = st.selectbox("Тип оплаты", ["Белая", "Черная", "Серая"], index=["Белая", "Черная", "Серая"].index(o.get("Тип", "Черная")), key=f"ot_{i}_{m_key}")
        m_store["staff_office"][i]["Тип"] = pay_type
        if pay_type == "Серая":
            m_store["staff_office"][i]["Оф_часть"] = st.number_input("Офиц. часть (на карту)", value=float(o.get("Оф_часть", 0.0)), key=f"oo_{i}_{m_key}")
        
        if st.button("Удалить сотрудника", key=f"o_del_{i}_{m_key}"): remove_office(i)
st.sidebar.button("➕ Добавить сотрудника офиса", on_click=add_office)

# --- ГЛАВНАЯ ПАНЕЛЬ ---
st.title(f"🍕 {sel_month_name} {sel_year}")
col_p1, col_p2, col_p3 = st.columns(3)
with col_p1: 
    p_b_sale = st.number_input("План продаж основ", value=int(m_store["plans"]["pb"]), key=f"v_pb_s_{m_key}")
    if p_b_sale != m_store["plans"]["pb"]: m_store["plans"]["pb"] = p_b_sale; save_data()
with col_p2: 
    p_p_sale = st.number_input("План продаж пиццы", value=int(m_store["plans"]["pp"]), key=f"v_pp_s_{m_key}")
    if p_p_sale != m_store["plans"]["pp"]: m_store["plans"]["pp"] = p_p_sale; save_data()
with col_p3: 
    idx_mode = 0 if m_store["plans"]["mode"] == "1 смена (12ч)" else 1
    w_mode = st.radio("Режим смен", ["1 смена (12ч)", "2 смены (24ч)"], index=idx_mode, horizontal=True, key=f"v_wm_{m_key}")
    if w_mode != m_store["plans"]["mode"]: m_store["plans"]["mode"] = w_mode; save_data()
    s_p_d = 1 if "1" in w_mode else 2

total_b = p_b_sale + p_p_sale
max_b = num_days * s_p_d * b_limit
max_p = num_days * s_p_d * a_shok * p_limit

st.divider()
st_c1, st_c2, st_c3 = st.columns(3)
with st_c1:
    b_ok = total_b <= max_b
    st.metric("Выпечка основ", f"{total_b} шт", delta=f"Предел: {max_b}", delta_color="normal" if b_ok else "inverse")
with st_c2:
    p_ok = p_p_sale <= max_p
    st.metric("Сборка пицц", f"{p_p_sale} шт", delta=f"Предел: {max_p}", delta_color="normal" if p_ok else "inverse")
with st_c3: st.metric("Для продажи", f"{p_b_sale} шт")
if not b_ok: st.error("🛑 Перегруз печей!")
if not p_ok: st.error("🛑 Превышение лимита сборки!")

curr_params = (total_b, p_p_sale, b_limit, p_limit, s_p_d, num_days, str(m_store["staff_bakers"]), str(m_store["staff_assemblers"]))
if m_key not in st.session_state.history or st.session_state.get(f"lp_{m_key}") != curr_params:
    st.session_state.history[m_key] = generate_auto_schedule(total_b, p_p_sale, b_limit, p_limit, s_p_d, num_days, m_store["staff_bakers"], m_store["staff_assemblers"])
    st.session_state[f"lp_{m_key}"] = curr_params
    save_data()

with st.expander("📅 Редактирование табелей", expanded=False):
    edited_df = st.data_editor(st.session_state.history[m_key], use_container_width=True, key=f"ed_{m_key}")
    if not edited_df.equals(st.session_state.history[m_key]):
        st.session_state.history[m_key] = edited_df
        save_data()

def get_circle(h):
    if h == 12: return '<span style="color: #28a745; white-space: nowrap;">🟢 12ч</span>'
    if h == 6:  return '<span style="color: #ffc107; white-space: nowrap;">🟡 6ч</span>'
    if h > 0:   return f'<span style="color: #fd7e14; white-space: nowrap;">🟠 {int(h) if h == int(h) else h}ч</span>'
    return '<span style="color: #6c757d; white-space: nowrap;">⚪ 0ч</span>'

def format_rub(x):
    return f"{int(x):,} ₽".replace(",", " ")

with st.expander("📋 Визуальный контроль смен", expanded=True):
    t_b, t_a = st.tabs(["👨‍🍳 Цех выпечки", "🛠️ Цех сборки"])
    st.markdown("""
        <style>
        .scroll-container { width: 100%; overflow-x: auto; border: 1px solid #444; border-radius: 5px; margin-bottom: 20px; }
        .scroll-container table { width: 100%; border-collapse: collapse; }
        .scroll-container th, .scroll-container td { text-align: center; padding: 8px; border: 1px solid #444; white-space: nowrap; }
        </style>
    """, unsafe_allow_html=True)
    b_names = [b["Имя"] for b in m_store["staff_bakers"]]
    a_names = [a["Имя"] for a in m_store["staff_assemblers"]]
    with t_b:
        df_b = st.session_state.history[m_key].loc[st.session_state.history[m_key].index.intersection(b_names)]
        if not df_b.empty:
            html_table = df_b.map(get_circle).to_html(escape=False)
            st.markdown(f'<div class="scroll-container">{html_table}</div>', unsafe_allow_html=True)
    with t_a:
        df_a = st.session_state.history[m_key].loc[st.session_state.history[m_key].index.intersection(a_names)]
        if not df_a.empty:
            html_table = df_a.map(get_circle).to_html(escape=False)
            st.markdown(f'<div class="scroll-container">{html_table}</div>', unsafe_allow_html=True)

st.subheader("💰 Ведомость выплат")

cur_df = st.session_state.history[m_key]
# Приводим индексы к числам для удобства срезов
cur_df.columns = [int(c) for c in cur_df.columns]

def calculate_payroll(staff_list, df):
    results = []
    for e in staff_list:
        name = e["Имя"]
        if name in df.index:
            row = df.loc[name]
            h1 = row.loc[[d for d in row.index if d <= 15]].sum()
            p1 = (h1/12) * e["Ставка"]
            h2 = row.loc[[d for d in row.index if d > 15]].sum()
            p2 = (h2/12) * e["Ставка"]
            
            total_hours = row.sum()
            total_money = p1 + p2
            pay_type = e.get("Тип", "Черная")
            official_total = 0.0
            if pay_type == "Белая": official_total = total_money
            elif pay_type == "Серая": official_total = float(e.get("Оф_часть", 0.0))
            
            off_p1 = official_total * 0.5
            off_p2 = official_total * 0.5
            env_p1 = max(0.0, p1 - off_p1)
            env_p2 = max(0.0, p2 - off_p2)
            
            results.append({
                "Сотрудник": name,
                "Часы (факт)": int(total_hours),
                "Аванс (Безнал)": int(off_p1),
                "Аванс (Нал)": int(env_p1),
                "Расчет (Безнал)": int(off_p2),
                "Расчет (Нал)": int(env_p2),
                "Итого": int(total_money)
            })
    return pd.DataFrame(results)

res_b = calculate_payroll(m_store["staff_bakers"], cur_df)
res_a = calculate_payroll(m_store["staff_assemblers"], cur_df)

# Офисные сотрудники: делим оклад 50/50 на аванс и расчет
res_o = []
for e in m_store.get("staff_office", []):
    oklad = e["Оклад"]
    p1 = oklad * 0.5
    p2 = oklad * 0.5
    total = oklad
    
    pay_type = e.get("Тип", "Черная")
    official_total = 0.0
    if pay_type == "Белая": official_total = total
    elif pay_type == "Серая": official_total = float(e.get("Оф_часть", 0.0))

    off_p1 = official_total * 0.5
    off_p2 = official_total * 0.5
    env_p1 = max(0.0, p1 - off_p1)
    env_p2 = max(0.0, p2 - off_p2)

    res_o.append({
        "Сотрудник": e["Имя"],
        "Аванс (Безнал)": int(off_p1),
        "Аванс (Нал)": int(env_p1),
        "Расчет (Безнал)": int(off_p2),
        "Расчет (Нал)": int(env_p2),
        "Итого": int(total)
    })
res_o = pd.DataFrame(res_o)

# CSS для центровки колонок в st.dataframe
st.markdown("""
    <style>
    /* Центрирование заголовков и ячеек в st.dataframe */
    [data-testid="stDataFrame"] td, 
    [data-testid="stDataFrame"] th,
    [data-testid="stTable"] td,
    [data-testid="stTable"] th {
        text-align: center !important;
    }
    /* Дополнительное правило для выравнивания текста внутри ячеек */
    div[data-testid="stExpander"] div[role="row"] div[role="cell"] {
        justify-content: center !important;
        text-align: center !important;
    }
    </style>
    """, unsafe_allow_html=True)

t1, t2, t3 = st.tabs(["👨‍🍳 Цех выпечки", "🛠️ Цех сборки", "🏢 Офис"])

def generate_pay_slip(name, data):
    summary = f"""
    *** РАСЧЕТНЫЙ ЛИСТОК: {name} ***
    Месяц: {sel_month_name} {sel_year}
    -----------------------------------
    АВАНС (выплата 20-го):
    - На карту (Безнал): {format_rub(data['Аванс (Безнал)'])}
    - В конверт (Нал): {format_rub(data['Аванс (Нал)'])}
    
    РАСЧЕТ (выплата 5-го):
    - На карту (Безнал): {format_rub(data['Расчет (Безнал)'])}
    - В конверт (Нал): {format_rub(data['Расчет (Нал)'])}
    -----------------------------------
    ИТОГО ЗА МЕСЯЦ: {format_rub(data['Итого'])}
    """
    return summary

with t1:
    if not res_b.empty:
        styled_df = res_b.copy()
        cols_to_format = ["Аванс (Безнал)", "Аванс (Нал)", "Расчет (Безнал)", "Расчет (Нал)", "Итого"]
        for col in cols_to_format:
            styled_df[col] = styled_df[col].apply(lambda x: format_rub(x))
        
        html = styled_df.to_html(index=False, escape=False)
        html = html.replace('<thead>', '<thead style="background-color: #ffffff; color: #000000;">')
        html = html.replace('<table>', '<table style="width:100%; border-collapse: collapse; text-align: center; color: white;">')
        html = html.replace('<th>', '<th style="text-align: center; padding: 12px; border: 1px solid #444; color: #000000;">')
        html = html.replace('<td>', '<td style="text-align: center; padding: 10px; border: 1px solid #444;">')
        st.markdown(html, unsafe_allow_html=True)
        
        s_a_bez = res_b["Аванс (Безнал)"].sum()
        s_a_nal = res_b["Аванс (Нал)"].sum()
        s_r_bez = res_b["Расчет (Безнал)"].sum()
        s_r_nal = res_b["Расчет (Нал)"].sum()
    else: s_a_bez = s_a_nal = s_r_bez = s_r_nal = 0

with t2:
    if not res_a.empty:
        styled_df_a = res_a.copy()
        cols_to_format = ["Аванс (Безнал)", "Аванс (Нал)", "Расчет (Безнал)", "Расчет (Нал)", "Итого"]
        for col in cols_to_format:
            styled_df_a[col] = styled_df_a[col].apply(lambda x: format_rub(x))
            
        html_a = styled_df_a.to_html(index=False, escape=False)
        html_a = html_a.replace('<thead>', '<thead style="background-color: #ffffff; color: #000000;">')
        html_a = html_a.replace('<table>', '<table style="width:100%; border-collapse: collapse; text-align: center; color: white;">')
        html_a = html_a.replace('<th>', '<th style="text-align: center; padding: 12px; border: 1px solid #444; color: #000000;">')
        html_a = html_a.replace('<td>', '<td style="text-align: center; padding: 10px; border: 1px solid #444;">')
        st.markdown(html_a, unsafe_allow_html=True)

        s_a_bez += res_a["Аванс (Безнал)"].sum()
        s_a_nal += res_a["Аванс (Нал)"].sum()
        s_r_bez += res_a["Расчет (Безнал)"].sum()
        s_r_nal += res_a["Расчет (Нал)"].sum()

with t3:
    if not res_o.empty:
        styled_df_o = res_o.copy()
        cols_to_format = ["Аванс (Безнал)", "Аванс (Нал)", "Расчет (Безнал)", "Расчет (Нал)", "Итого"]
        for col in cols_to_format:
            styled_df_o[col] = styled_df_o[col].apply(lambda x: format_rub(x))
            
        html_o = styled_df_o.to_html(index=False, escape=False)
        html_o = html_o.replace('<thead>', '<thead style="background-color: #ffffff; color: #000000;">')
        html_o = html_o.replace('<table>', '<table style="width:100%; border-collapse: collapse; text-align: center; color: white;">')
        html_o = html_o.replace('<th>', '<th style="text-align: center; padding: 12px; border: 1px solid #444; color: #000000;">')
        html_o = html_o.replace('<td>', '<td style="text-align: center; padding: 10px; border: 1px solid #444;">')
        st.markdown(html_o, unsafe_allow_html=True)
        
        s_a_bez += res_o["Аванс (Безнал)"].sum()
        s_a_nal += res_o["Аванс (Нал)"].sum()
        s_r_bez += res_o["Расчет (Безнал)"].sum()
        s_r_nal += res_o["Расчет (Нал)"].sum()

st.divider()
c_total1, c_total2 = st.columns(2)
with c_total1:
    st.markdown("#### 📅 К 20-МУ ЧИСЛУ (АВАНС)")
    st.write(f"💳 По безналу: **{format_rub(s_a_bez)}**")
    st.write(f"💰 Наличными: **{format_rub(s_a_nal)}**")
    st.metric("ИТОГО АВАНС", format_rub(s_a_bez + s_a_nal))
with c_total2:
    st.markdown("#### 📅 К 5-МУ ЧИСЛУ (РАСЧЕТ)")
    st.write(f"💳 По безналу: **{format_rub(s_r_bez)}**")
    st.write(f"💰 Наличными: **{format_rub(s_r_nal)}**")
    st.metric("ИТОГО РАСЧЕТ", format_rub(s_r_bez + s_r_nal))

st.divider()
st.metric("ОБЩИЙ ФОНД МЕСЯЦА", format_rub(s_a_bez + s_a_nal + s_r_bez + s_r_nal))
