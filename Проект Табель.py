import streamlit as st
import pandas as pd
import numpy as np
import calendar
import json
import os
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
            data = json.load(f)
            # Конвертируем JSON обратно в DataFrame для истории
            if "history" in data:
                for k in data["history"]:
                    data["history"][k] = pd.DataFrame(data["history"][k])
            return data
    return {"history": {}, "month_data": {}}

def save_data():
    data_to_save = {
        "history": {k: v.to_dict() for k, v in st.session_state.history.items()},
        "month_data": st.session_state.month_data
    }
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=4)
    
    # Проверка необходимости бэкапа (раз в час)
    last_backup = st.session_state.get("last_backup", 0)
    if time.time() - last_backup > 3600:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"backup_{ts}.json"
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False)
        st.session_state.last_backup = time.time()

# --- ИНИЦИАЛИЗАЦИЯ ---
if 'initialized' not in st.session_state:
    saved = load_data()
    st.session_state.history = saved["history"]
    st.session_state.month_data = saved["month_data"]
    st.session_state.initialized = True

# --- ЛОКАЛИЗАЦИЯ МЕСЯЦЕВ ---
MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}

# --- СОСТОЯНИЕ СОТРУДНИКОВ ---
def get_month_data(m_key):
    if m_key not in st.session_state.month_data:
        st.session_state.month_data[m_key] = {
            "staff_bakers": [{"Имя": f"Пекарь {i+1}", "Ставка": 3500.0, "Начало": 1} for i in range(6)],
            "staff_assemblers": [{"Имя": f"Сборщик {i+1}", "Ставка": 3000.0, "Начало": 1} for i in range(4)],
            "plans": {"pb": 30000, "pp": 10000, "mode": "1 смена (12ч)"}
        }
    return st.session_state.month_data[m_key]

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

# --- ЛОГИКА ГЕНЕРАЦИИ ГРАФИКА ---
def generate_auto_schedule(plan_bases_total, plan_pizza, b_perf, a_perf, shifts_day, n_days, bakers, assemblers):
    b_shifts_needed = int(np.ceil(plan_bases_total / b_perf / shifts_day)) if b_perf > 0 else 0
    p_shifts_total = int(np.ceil(plan_pizza / a_perf)) if a_perf > 0 else 0
    num_a = len(assemblers)
    shifts_per_assm = int(np.ceil(p_shifts_total / num_a / shifts_day)) if num_a > 0 else 0
    schedule = {}
    for emp in bakers:
        s = emp.get("Начало", 1)
        avail = n_days - s + 1
        indices = np.linspace(s-1, n_days-1, min(b_shifts_needed, avail), dtype=int) if avail > 0 else []
        row = [0.0] * n_days
        for idx in indices: row[idx] = 12.0
        schedule[emp["Имя"]] = row
    for emp in assemblers:
        s = emp.get("Начало", 1)
        avail = n_days - s + 1
        indices = np.linspace(s-1, n_days-1, min(shifts_per_assm * shifts_day, avail), dtype=int) if avail > 0 else []
        row = [0.0] * n_days
        for idx in indices: row[idx] = 12.0
        schedule[emp["Имя"]] = row
    return pd.DataFrame(schedule, index=range(1, n_days+1)).T

# --- БОКОВАЯ ПАНЕЛЬ ---
st.sidebar.header("⚙️ Настройки")

with st.sidebar.expander("🏗️ Параметры производства", expanded=False):
    b_limit = st.number_input("Макс. основ/смену", value=1800)
    p_limit = st.number_input("Пицц на сборщика", value=250)
    a_shok = st.number_input("Макс кол-во сборщиков", value=4)

st.sidebar.markdown("---")
st.sidebar.subheader("👨‍🍳 Цех выпечки")
c_hb1, c_hb2, c_hb3, _ = st.sidebar.columns([3, 2, 2, 1])
c_hb1.caption("Должность"); c_hb2.caption("Оклад"); c_hb3.caption("С дня")
for i, b in enumerate(m_store["staff_bakers"]):
    c1, c2, c3, c4 = st.sidebar.columns([3, 2, 2, 1])
    m_store["staff_bakers"][i]["Имя"] = c1.text_input(f"bn_{i}", b["Имя"], key=f"v_bn_{i}_{m_key}", label_visibility="collapsed")
    m_store["staff_bakers"][i]["Ставка"] = c2.number_input(f"bs_{i}", value=float(b["Ставка"]), key=f"v_bs_{i}_{m_key}", label_visibility="collapsed")
    m_store["staff_bakers"][i]["Начало"] = c3.number_input(f"bd_{i}", 1, num_days, int(b.get("Начало", 1)), key=f"v_bd_s_{i}_{m_key}", label_visibility="collapsed")
    if c4.button("❌", key=f"bd_del_{i}_{m_key}"): remove_baker(i)
st.sidebar.button("➕ Добавить пекаря", on_click=add_baker)

st.sidebar.divider(); st.sidebar.subheader("🛠️ Цех сборки")
c_ha1, c_ha2, c_ha3, _ = st.sidebar.columns([3, 2, 2, 1])
c_ha1.caption("Должность"); c_ha2.caption("Оклад"); c_ha3.caption("С дня")
for i, a in enumerate(m_store["staff_assemblers"]):
    c1, c2, c3, c4 = st.sidebar.columns([3, 2, 2, 1])
    m_store["staff_assemblers"][i]["Имя"] = c1.text_input(f"an_{i}", a["Имя"], key=f"v_an_{i}_{m_key}", label_visibility="collapsed")
    m_store["staff_assemblers"][i]["Ставка"] = c2.number_input(f"as_{i}", value=float(a["Ставка"]), key=f"v_as_{i}_{m_key}", label_visibility="collapsed")
    m_store["staff_assemblers"][i]["Начало"] = c3.number_input(f"ad_{i}", 1, num_days, int(a.get("Начало", 1)), key=f"v_ad_s_{i}_{m_key}", label_visibility="collapsed")
    if c4.button("❌", key=f"ad_del_{i}_{m_key}"): remove_assembler(i)
st.sidebar.button("➕ Добавить сборщика", on_click=add_assembler)

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

st.divider(); st_c1, st_c2, st_c3 = st.columns(3)
with st_c1:
    b_ok = total_b <= max_b
    st.metric("Выпечка основ", f"{total_b} шт", delta=f"Предел: {max_b}", delta_color="normal" if b_ok else "inverse")
with st_c2:
    p_ok = p_p_sale <= max_p
    st.metric("Сборка пицц", f"{p_p_sale} шт", delta=f"Предел: {max_p}", delta_color="normal" if p_ok else "inverse")
with st_c3: st.metric("Для продажи", f"{p_b_sale} шт")
if not b_ok: st.error("🛑 Перегруз печей!")
if not p_ok: st.error("🛑 Превышение лимита заморозки!")

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
    if h == 12: return '<span style="color: #28a745;">🟢 12ч</span>'
    if h == 6:  return '<span style="color: #ffc107;">🟡 6ч</span>'
    if h > 0:   return f'<span style="color: #fd7e14;">🟠 {int(h) if h == int(h) else h}ч</span>'
    return '<span style="color: #6c757d;">⚪ 0ч</span>'

with st.expander("📋 Визуальный контроль смен", expanded=True):
    t_b, t_a = st.tabs(["👨‍🍳 Цех выпечки", "🛠️ Цех сборки"])
    b_names = [b["Имя"] for b in m_store["staff_bakers"]]
    a_names = [a["Имя"] for a in m_store["staff_assemblers"]]
    with t_b:
        df_b = st.session_state.history[m_key][st.session_state.history[m_key].index.isin(b_names)]
        if not df_b.empty: st.write(df_b.map(get_circle).to_html(escape=False), unsafe_allow_html=True)
    with t_a:
        df_a = st.session_state.history[m_key][st.session_state.history[m_key].index.isin(a_names)]
        if not df_a.empty: st.write(df_a.map(get_circle).to_html(escape=False), unsafe_allow_html=True)

st.subheader("💰 Ведомость выплат")
b_r, a_r = [], []
cur_df = st.session_state.history[m_key]
for e in m_store["staff_bakers"]:
    if e["Имя"] in cur_df.index:
        h = cur_df.loc[e["Имя"]].sum(); p = (h/12)*e["Ставка"]
        b_r.append({"Сотрудник": e["Имя"], "Часы": int(h), "Зарплата": int(p)})
for e in m_store["staff_assemblers"]:
    if e["Имя"] in cur_df.index:
        h = cur_df.loc[e["Имя"]].sum(); p = (h/12)*e["Ставка"]
        a_r.append({"Сотрудник": e["Имя"], "Часы": int(h), "Зарплата": int(p)})

cv1, cv2 = st.columns(2)
with cv1:
    st.markdown("#### 👨‍🍳 Выпечка")
    if b_r:
        db = pd.DataFrame(b_r); tb = db.Зарплата.sum()
        db.Зарплата = db.Зарплата.apply(lambda x: f"{x:,} ₽".replace(",", " "))
        st.table(db); st.write(f"**Итого: {int(tb):,} ₽**".replace(",", " "))
    else: tb = 0
with cv2:
    st.markdown("#### 🛠️ Сборка")
    if a_r:
        da = pd.DataFrame(a_r); ta = da.Зарплата.sum()
        da.Зарплата = da.Зарплата.apply(lambda x: f"{x:,} ₽".replace(",", " "))
        st.table(da); st.write(f"**Итого: {int(ta):,} ₽**".replace(",", " "))
    else: ta = 0
st.divider(); st.metric("ОБЩИЙ ФОНД ВЫПЛАТ", f"{int(tb + ta):,} ₽".replace(",", " "))
