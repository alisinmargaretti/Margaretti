import streamlit as st
import pandas as pd
import numpy as np
import calendar
import json
import time
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
from pathlib import Path

st.set_page_config(page_title="Пицца-Про: Учет производства", layout="wide")

DB_FILE = Path("production_data.json")

# --- СИСТЕМА ХРАНЕНИЯ ДАННЫХ (GOOGLE SHEETS + LOCAL) ---
def load_data():
    # 1. Сначала пробуем загрузить из Google Sheets
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        existing_data = conn.read(worksheet="Sheet1", ttl=0)
        if not existing_data.empty and existing_data.shape[1] > 0:
            raw_json = str(existing_data.iloc[0, 0])
            data = json.loads(raw_json)
            if "history" in data:
                for k in data["history"]:
                    data["history"][k] = pd.DataFrame(data["history"][k])
            return data
    except Exception as e:
        # 2. Если Google не доступен, пробуем локальный файл
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
    # Подготовка данных для сохранения
    data_to_save = {
        "history": {k: v.to_dict() for k, v in st.session_state.history.items()},
        "month_data": st.session_state.month_data
    }
    json_string = json.dumps(data_to_save, ensure_ascii=False)
    
    # 1. Сохраняем локально (для кэша)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        f.write(json_string)
    
    # 2. Сохраняем в Google Sheets
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        # Создаем DataFrame из одной ячейки с JSON
        df_to_save = pd.DataFrame([json_string])
        conn.update(worksheet="Sheet1", data=df_to_save)
    except Exception as e:
        st.error(f"Ошибка сохранения в облако: {e}")

# --- ИНИЦИАЛИЗАЦИЯ ---
if 'initialized' not in st.session_state:
    saved = load_data()
    st.session_state.history = saved.get("history", {})
    st.session_state.month_data = saved.get("month_data", {})
    st.session_state.initialized = True

MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}

def get_month_data(m_key):
    if m_key not in st.session_state.month_data:
        st.session_state.month_data[m_key] = {
            "staff_bakers": [{"Имя": f"Пекарь {i+1}", "Ставка": 3500.0, "Начало": 1} for i in range(6)],
            "staff_assemblers": [{"Имя": f"Сборщик {i+1}", "Ставка": 3000.0, "Начало": 1} for i in range(4)],
            "plans": {"pb": 30000, "pp": 10000, "mode": "1 смена (12ч)"}
        }
    return st.session_state.month_data[m_key]

# --- БОКОВАЯ ПАНЕЛЬ ---
now = datetime.now()
sel_month_name = st.sidebar.selectbox("📅 Месяц", list(MONTHS_RU.values()), index=now.month-1)
sel_month_idx = [k for k, v in MONTHS_RU.items() if v == sel_month_name][0]
sel_year = st.sidebar.number_input("Год", value=now.year)
m_key = f"{sel_month_idx}_{sel_year}"
m_store = get_month_data(m_key)
num_days = calendar.monthrange(sel_year, sel_month_idx)[1]

def add_baker(): m_store["staff_bakers"].append({"Имя": "Новый пекарь", "Ставка": 3500.0, "Начало": 1}); save_data()
def add_assembler(): m_store["staff_assemblers"].append({"Имя": "Новый сборщик", "Ставка": 3000.0, "Начало": 1}); save_data()
def remove_baker(index): m_store["staff_bakers"].pop(index); save_data(); st.rerun()
def remove_assembler(index): m_store["staff_assemblers"].pop(index); save_data(); st.rerun()

def generate_auto_schedule(plan_bases_total, plan_pizza, b_perf, a_perf, shifts_day, n_days, bakers, assemblers):
    b_shifts_needed = int(np.ceil(plan_bases_total / b_perf / shifts_day)) if b_perf > 0 else 0
    common_b_days = np.linspace(0, n_days - 1, min(b_shifts_needed, n_days), dtype=int) if b_shifts_needed > 0 else []
    
    schedule = {}
    for emp in bakers:
        s_idx = emp.get("Начало", 1) - 1
        row = [0.0] * n_days
        for d_idx in common_b_days:
            if d_idx >= s_idx: row[d_idx] = 12.0
        schedule[emp["Имя"]] = row

    p_shifts_total = int(np.ceil(plan_pizza / a_perf)) if a_perf > 0 else 0
    num_a = len(assemblers)
    shifts_per_assm = int(np.ceil(p_shifts_total / num_a / shifts_day)) if num_a > 0 else 0
    for emp in assemblers:
        s = emp.get("Начало", 1)
        avail = n_days - s + 1
        indices = np.linspace(s-1, n_days-1, min(shifts_per_assm * shifts_day, avail), dtype=int) if avail > 0 else []
        row = [0.0] * n_days
        for idx in indices: row[idx] = 12.0
        schedule[emp["Имя"]] = row
    return pd.DataFrame(schedule, index=range(1, n_days+1)).T

with st.sidebar.expander("🏗️ Настройки цеха", expanded=False):
    b_limit = st.number_input("Макс. основ/смену", value=1800)
    p_limit = st.number_input("Пицц на сборщика", value=250)
    a_shok = st.number_input("Количество сборщиков", value=4)

st.sidebar.markdown("---")
st.sidebar.subheader("👨‍🍳 Цех выпечки")
for i, b in enumerate(m_store["staff_bakers"]):
    c1, c2, c3, c4 = st.sidebar.columns([3, 2, 2, 1])
    m_store["staff_bakers"][i]["Имя"] = c1.text_input(f"bn_{i}", b["Имя"], key=f"bn_{i}_{m_key}", label_visibility="collapsed")
    m_store["staff_bakers"][i]["Ставка"] = c2.number_input(f"bs_{i}", value=float(b["Ставка"]), key=f"bs_{i}_{m_key}", label_visibility="collapsed")
    m_store["staff_bakers"][i]["Начало"] = c3.number_input(f"bd_{i}", 1, num_days, int(b.get("Начало", 1)), key=f"bd_{i}_{m_key}", label_visibility="collapsed")
    if c4.button("❌", key=f"b_del_{i}_{m_key}"): remove_baker(i)
st.sidebar.button("➕ Добавить пекаря", on_click=add_baker)

st.sidebar.divider()
st.sidebar.subheader("🛠️ Цех сборки")
for i, a in enumerate(m_store["staff_assemblers"]):
    c1, c2, c3, c4 = st.sidebar.columns([3, 2, 2, 1])
    m_store["staff_assemblers"][i]["Имя"] = c1.text_input(f"an_{i}", a["Имя"], key=f"an_{i}_{m_key}", label_visibility="collapsed")
    m_store["staff_assemblers"][i]["Ставка"] = c2.number_input(f"as_{i}", value=float(a["Ставка"]), key=f"as_{i}_{m_key}", label_visibility="collapsed")
    m_store["staff_assemblers"][i]["Начало"] = c3.number_input(f"ad_{i}", 1, num_days, int(a.get("Начало", 1)), key=f"ad_{i}_{m_key}", label_visibility="collapsed")
    if c4.button("❌", key=f"a_del_{i}_{m_key}"): remove_assembler(i)
st.sidebar.button("➕ Добавить сборщика", on_click=add_assembler)

# --- ГЛАВНАЯ ПАНЕЛЬ ---
st.title(f"🍕 {sel_month_name} {sel_year}")
col_p1, col_p2, col_p3 = st.columns(3)
with col_p1: 
    p_b_sale = st.number_input("План продаж основ", value=int(m_store["plans"]["pb"]), key=f"p_b_{m_key}")
    if p_b_sale != m_store["plans"]["pb"]: m_store["plans"]["pb"] = p_b_sale; save_data()
with col_p2: 
    p_p_sale = st.number_input("План продаж пиццы", value=int(m_store["plans"]["pp"]), key=f"p_p_{m_key}")
    if p_p_sale != m_store["plans"]["pp"]: m_store["plans"]["pp"] = p_p_sale; save_data()
with col_p3: 
    idx_mode = 0 if m_store["plans"]["mode"] == "1 смена (12ч)" else 1
    w_mode = st.radio("Режим смен", ["1 смена (12ч)", "2 смены (24ч)"], index=idx_mode, horizontal=True, key=f"w_m_{m_key}")
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

with st.expander("📋 Визуальный контроль смен", expanded=True):
    t_b, t_a = st.tabs(["👨‍🍳 Цех выпечки", "🛠️ Цех сборки"])
    st.markdown("<style>.scroll-container { width: 100%; overflow-x: auto; border: 1px solid #444; border-radius: 5px; margin-bottom: 20px; } table { width: 100%; border-collapse: collapse; } th, td { text-align: center; padding: 8px; border: 1px solid #444; white-space: nowrap; }</style>", unsafe_allow_html=True)
    b_names = [b["Имя"] for b in m_store["staff_bakers"]]
    a_names = [a["Имя"] for a in m_store["staff_assemblers"]]
    with t_b:
        df_b = st.session_state.history[m_key].loc[st.session_state.history[m_key].index.intersection(b_names)]
        if not df_b.empty:
            st.markdown(f'<div class="scroll-container">{df_b.map(get_circle).to_html(escape=False)}</div>', unsafe_allow_html=True)
    with t_a:
        df_a = st.session_state.history[m_key].loc[st.session_state.history[m_key].index.intersection(a_names)]
        if not df_a.empty:
            st.markdown(f'<div class="scroll-container">{df_a.map(get_circle).to_html(escape=False)}</div>', unsafe_allow_html=True)

st.subheader("💰 Ведомость выплат")
b_r, a_r = [], []
cur_df = st.session_state.history[m_key]
for e in m_store["staff_bakers"]:
    if e["Имя"] in cur_df.index:
        h = cur_df.loc[e["Имя"]].sum()
        b_r.append({"Сотрудник": e["Имя"], "Часы": int(h), "Зарплата": int((h/12)*e["Ставка"])})
for e in m_store["staff_assemblers"]:
    if e["Имя"] in cur_df.index:
        h = cur_df.loc[e["Имя"]].sum()
        a_r.append({"Сотрудник": e["Имя"], "Часы": int(h), "Зарплата": int((h/12)*e["Ставка"])})
cv1, cv2 = st.columns(2)
with cv1:
    st.markdown("#### 👨‍🍳 Выпечка")
    if b_r:
        df_br = pd.DataFrame(b_r)
        tb = df_br.Зарплата.sum()
        st.table(df_br.assign(Зарплата=df_br.Зарплата.apply(lambda x: f"{x:,} ₽".replace(",", " "))))
        st.write(f"**Итого: {int(tb):,} ₽**".replace(",", " "))
    else: tb = 0
with cv2:
    st.markdown("#### 🛠️ Сборка")
    if a_r:
        df_ar = pd.DataFrame(a_r)
        ta = df_ar.Зарплата.sum()
        st.table(df_ar.assign(Зарплата=df_ar.Зарплата.apply(lambda x: f"{x:,} ₽".replace(",", " "))))
        st.write(f"**Итого: {int(ta):,} ₽**".replace(",", " "))
    else: ta = 0
st.divider()
st.metric("ОБЩИЙ ФОНД ВЫПЛАТ", f"{int(tb + ta):,} ₽".replace(",", " "))
