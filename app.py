
import streamlit as st
import pandas as pd
from data_loader import load_weekly_data, calculate_player_metrics, calculate_defense_rankings

st.set_page_config(page_title="NFL Mismatch Finder", layout="wide")

st.title("🏈 NFL Mismatch Finder — Dynamic Betting Dashboard")

@st.cache_data(ttl=3600)
def get_data():
    raw_data = load_weekly_data(years=[2025])
    players_data = calculate_player_metrics(raw_data)
    defense_data = calculate_defense_rankings(raw_data)
    return players_data, defense_data

with st.spinner("Chargement des données NFL en cours..."):
    players_df, defense_df = get_data()

# Sidebar - Filtres
st.sidebar.header("Filtres")
selected_position = st.sidebar.multiselect("Position", options=["QB", "RB", "WR", "TE"], default=["WR", "RB"])
stat_type = st.sidebar.selectbox("Pari ciblé", options=["Receiving Yards", "Rushing Yards", "Passing Yards"])

# Filtrer les joueurs récents (dernière semaine disponible)
latest_week = players_df['week'].max()
df_latest = players_df[(players_df['week'] == latest_week) & (players_df['position'].isin(selected_position))].copy()

# Jointure avec la défense adverse
df_merged = pd.merge(
    df_latest,
    defense_df,
    left_on='opponent_team',
    right_on='opponent_team',
    how='left'
)

# Alignement des colonnes selon le pari ciblé
if stat_type == "Receiving Yards":
    metric_season = "receiving_yards"
    metric_l3 = "receiving_yards_L3"
    def_rank_col = "pass_def_rank"
elif stat_type == "Rushing Yards":
    metric_season = "rushing_yards"
    metric_l3 = "rushing_yards_L3"
    def_rank_col = "rush_def_rank"
else:
    metric_season = "passing_yards"
    metric_l3 = "passing_yards_L3"
    def_rank_col = "pass_def_rank"

# Détection automatique des Mismatches (Pire défense = Rank > 24)
df_merged['Mismatch Alert'] = df_merged[def_rank_col].apply(lambda x: "🔥 TOP MISMATCH" if x >= 24 else ("⚠️ Mismatch Moyen" if x >= 16 else "OK"))

# Affichage du tableau principal
st.subheader(f"Analyses & Projections : {stat_type} (Semaine {latest_week})")

columns_to_show = [
    'player_name', 'position', 'team', 'opponent_team', 'status',
    metric_season, metric_l3, def_rank_col, 'Mismatch Alert'
]

display_df = df_merged[columns_to_show].rename(columns={
    'player_name': 'Joueur',
    'position': 'Pos',
    'team': 'Équipe',
    'opponent_team': 'Adversaire',
    'status': 'Blessure',
    metric_season: 'Moy. Saison',
    metric_l3: 'Moy. Last 3',
    def_rank_col: 'Rang Def Adverse (1=Top, 32=Pire)',
    'Mismatch Alert': 'Indicateur'
}).sort_values(by='Moy. Last 3', ascending=False)

st.dataframe(
    display_df,
    use_container_width=True,
    column_config={
        "Indicateur": st.column_config.TextColumn("Indicateur Mismatch")
    }
)

# Section Classement Défense
with st.expander("📊 Voir le classement complet des défenses"):
    st.dataframe(defense_df.sort_values(by='pass_def_rank', ascending=False), use_container_width=True)
