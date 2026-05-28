import streamlit as st
import sqlite3
import hashlib
import pandas as pd
import plotly.graph_objects as go
import copy
from datetime import datetime

# -----------------------------
# CONFIG VISUAL
# -----------------------------
st.set_page_config(page_title="Carteira de Investimentos", layout="wide")

st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-left: 2rem;
    padding-right: 2rem;
}

@media (max-width: 768px) {
    .stDataFrame {
        font-size: 12px;
    }
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# DB
# -----------------------------
conn = sqlite3.connect("carteira.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS investments (
    user TEXT,
    nome TEXT,
    categoria TEXT,
    valor REAL,
    entrada REAL,
    rent REAL,
    tipo_rent TEXT,
    meta REAL,
    vencimento TEXT
)
""")

conn.commit()

# -----------------------------
# FUNÇÕES
# -----------------------------
def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def create_user(u, p):
    try:
        c.execute("INSERT INTO users VALUES (?,?)", (u, hash_password(p)))
        conn.commit()
        return True
    except:
        return False

def login(u, p):
    c.execute("SELECT password FROM users WHERE username=?", (u,))
    d = c.fetchone()
    return d and d[0] == hash_password(p)

# -----------------------------
# SIMULAÇÃO APORTE
# -----------------------------
def calcular_aporte_necessario(meta, valor_atual, meses, taxa_mensal):
    if meses <= 0:
        return 0

    fator = (1 + taxa_mensal) ** meses

    if taxa_mensal == 0:
        return max((meta - valor_atual) / meses, 0)

    try:
        pmt = (meta - valor_atual * fator) * taxa_mensal / (fator - 1)
        return max(pmt, 0)
    except:
        return 0

# -----------------------------
# LOGIN
# -----------------------------
if "user" not in st.session_state:

    st.title("💰 Carteira de Investimentos")
    st.subheader("Acesse sua conta")

    user = st.text_input("Usuário")
    pwd = st.text_input("Senha", type="password")

    col1, col2 = st.columns(2)

    if col1.button("Entrar"):
        if login(user, pwd):
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Login inválido")

    if col2.button("Criar conta"):
        if create_user(user, pwd):
            st.success("Conta criada!")
        else:
            st.error("Usuário já existe")

    st.stop()

# -----------------------------
# USUÁRIO
# -----------------------------
user = st.session_state.user

df = pd.read_sql(
    "SELECT rowid, * FROM investments WHERE user=?",
    conn,
    params=(user,)
)

# -----------------------------
# TIPOS
# -----------------------------
TIPOS = [
    "Tesouro Selic", "Tesouro IPCA+", "Tesouro Prefixado",
    "CDB", "LCI", "LCA", "Debêntures", "CRI/CRA",
    "FII", "Ações", "ETF", "BDR",
    "Criptomoedas", "Dólar", "Ouro",
    "Fundos Imobiliários", "Fundos Multimercado",
    "Previdência Privada", "Conta remunerada",
    "Poupança", "Outro"
]

# -----------------------------
# MENU
# -----------------------------
st.sidebar.title("📊 Menu")

menu = st.sidebar.radio(
    "Navegação",
    ["🏠 Início", "➕ Adicionar investimento", "📂 Carteira", "🗑️ Remover investimentos"]
)

# -----------------------------
# HOME
# -----------------------------
if menu == "🏠 Início":

    st.title("📊 Carteira de Investimentos")
    st.write(f"Bem-vindo, **{user}** 👋")

    if not df.empty:
        sim = copy.deepcopy(df)

        meses = 120
        serie = []

        for _ in range(meses):
            total = 0
            for i in range(len(sim)):
                sim.at[i, "valor"] = sim.at[i, "valor"] * (1 + sim.at[i, "rent"])
                sim.at[i, "valor"] += sim.at[i, "entrada"]
                total += sim.at[i, "valor"]
            serie.append(total)

        fig = go.Figure()
        fig.add_trace(go.Scatter(y=serie, mode="lines", line=dict(width=4)))

        fig.update_layout(template="plotly_dark", height=420)

        st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# ADD INVESTIMENTO INTELIGENTE
# -----------------------------
elif menu == "➕ Adicionar investimento":

    st.title("➕ Novo investimento")

    col1, col2 = st.columns(2)

    nome = col1.text_input("Nome")
    categoria = col2.selectbox("Tipo de investimento", TIPOS)

    valor = st.number_input("Valor atual (R$)", 0.0)

    meta = st.number_input("Meta (R$)", 0.0)
    venc = st.date_input(
        "Data de vencimento",
        min_value=datetime(2000, 1, 1),
        max_value=datetime(2099, 12, 31)
    )

    rent = st.number_input("Rentabilidade anual (%)", min_value=0.0, value=10.0)
    rent_m = rent / 100 / 12

    hoje = datetime.today()
    meses = max(1, (venc - hoje.date()).days // 30)

    recomendado = 0

    if meta > 0:
        recomendado = calcular_aporte_necessario(meta, valor, meses, rent_m)

        st.info(
            f"📊 Para atingir R$ {meta:,.2f} até {venc}, "
            f"você precisaria de:\n\n"
            f"👉 R$ {recomendado:,.2f} por mês"
        )

    modo = st.radio(
        "Como deseja definir sua entrada mensal?",
        ["🔮 Usar recomendação", "✍️ Definir manualmente"]
    )

    if modo == "🔮 Usar recomendação":
        entrada = recomendado
        st.success(f"Entrada automática: R$ {entrada:,.2f}")
    else:
        entrada = st.number_input("Entrada mensal (R$)", 0.0)

    if st.button("Salvar investimento"):

        entrada = max(0.0, entrada)
        rent_m = max(0.0, rent_m)

        c.execute("""
        INSERT INTO investments VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            user, nome, categoria,
            valor, entrada,
            rent_m, "Mensal",
            meta, str(venc)
        ))

        conn.commit()
        st.success("✅ Investimento salvo!")
        st.rerun()

# -----------------------------
# CARTEIRA (COM GRÁFICO POR INVESTIMENTO)
# -----------------------------
elif menu == "📂 Carteira":

    st.title("📂 Seus investimentos")

    if df.empty:
        st.info("Nenhum investimento cadastrado.")
    else:
        st.dataframe(df.drop(columns=["rowid"]), use_container_width=True)

        st.divider()

        st.subheader("📊 Gráfico por investimento")

        investimento = st.selectbox(
            "Selecione um investimento",
            df["nome"].tolist()
        )

        inv = df[df["nome"] == investimento].iloc[0]

        valor = float(inv["valor"])
        entrada = float(inv["entrada"])
        rent = float(inv["rent"])

        meses = 120
        sim = valor
        serie = []

        for _ in range(meses):
            sim = sim * (1 + rent)
            sim += entrada
            serie.append(sim)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            y=serie,
            mode="lines",
            line=dict(width=4),
            name=investimento
        ))

        fig.update_layout(
            template="plotly_dark",
            height=400,
            margin=dict(l=10, r=10, t=20, b=20),
            yaxis_title="Valor (R$)"
        )

        st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# REMOVER
# -----------------------------
elif menu == "🗑️ Remover investimentos":

    st.title("🗑️ Remover investimentos")

    if df.empty:
        st.info("Nada para remover.")
    else:
        selecionados = st.multiselect(
            "Selecione os investimentos",
            options=df["rowid"],
            format_func=lambda x: df[df["rowid"] == x]["nome"].values[0]
        )

        if st.button("Excluir selecionados"):
            for rid in selecionados:
                c.execute("DELETE FROM investments WHERE rowid=?", (rid,))
            conn.commit()

            st.success("Removido com sucesso!")
            st.rerun()