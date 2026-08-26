import streamlit as st
import pandas as pd
from data_loader import load_data_for_2026_season, calculate_2025_player_baselines, calculate_2025_defense_rankings

st.set_page_config(page_title="NFL Mismatch Finder 2026", layout="wide")
st.title("🏈 NFL 2026 Mismatch Finder (Basé sur les stats 2025)")

@st.cache_data(ttl=3600)
def get_dashboard_data():
    df_2025, schedule_2026, roster_2026 = load_data_for_2026_season()
    player_baselines = calculate_2025_player_baselines(df_2025)
    def_rankings = calculate_2025_defense_rankings(df_2025)
    return player_baselines, schedule_2026, roster_2026, def_rankings

with st.spinner("Chargement du calendrier 2026 et des données 2025..."):
    players_df, schedule_2026, roster_2026, def_df = get_dashboard_data()

# Sidebar
st.sidebar.header("Paramètres 2026")

# Selecteur de semaine 2026
available_weeks = sorted(schedule_2026['week'].unique())
selected_week = st.sidebar.selectbox("Semaine NFL 2026", options=available_weeks, index=0)

selected_position = st.sidebar.multiselect("Position", options=["QB", "RB", "WR", "TE"], default=["WR", "RB"])
stat_type = st.sidebar.selectbox("Pari ciblé", options=["Receiving Yards", "Rushing Yards", "Passing Yards"])

# 1. Filtrer le calendrier 2026 pour la semaine sélectionnée
week_schedule = schedule_2026[schedule_2026['week'] == selected_week]

# Création des paires Matchup (Home vs Away) pour 2026
home_teams = week_schedule[['home_team', 'away_team', 'location']].rename(columns={'home_team': 'team', 'away_team': 'opponent_team'})
away_teams = week_schedule[['away_team', 'home_team', 'location']].rename(columns={'away_team': 'team', 'home_team': 'opponent_team'})
matchups_2026 = pd.concat([home_teams, away_teams])

# 2. Merger les joueurs actifs 2026 avec leur calendrier de la semaine
df_merged = pd.merge(roster_2026, matchups_2026, left_on='team', right_on='team', how='inner')
df_merged = df_merged[df_merged['position'].isin(selected_position)]

# 3. Merger les baselines 2025 du joueur
df_merged = pd.merge(df_merged, players_df, on='player_id', how='left')

# 4. Merger le rang 2025 de la défense adverse 2026
df_merged = pd.merge(df_merged, def_df, left_on='opponent_team', right_on='opponent_team', how='left')

# Sélection des métriques à afficher
if stat_type == "Receiving Yards":
    m_avg, m_l3, def_rank = "rec_yds_avg", "rec_yds_l3", "pass_def_rank_2025"
elif stat_type == "Rushing Yards":
    m_avg, m_l3, def_rank = "rush_yds_avg", "rush_yds_l3", "rush_def_rank_2025"
else:
    m_avg, m_l3, def_rank = "pass_yds_avg", "pass_yds_l3", "pass_def_rank_2025"

# Détection de Mismatch
df_merged['Mismatch Alert'] = df_merged[def_rank].apply(
    lambda x: "🔥 TOP MISMATCH" if x >= 24 else ("⚠️ Mismatch Moyen" if x >= 16 else "OK")
)

st.subheader(f"Matchups Semaine {selected_week} (Saison 2026)")

cols_display = ['player_name_x', 'position_x', 'team', 'opponent_team', m_avg, m_l3, def_rank, 'Mismatch Alert']

res_df = df_merged[cols_display].rename(columns={
    'player_name_x': 'Joueur',
    'position_x': 'Pos',
    'team': 'Équipe (2026)',
    'opponent_team': 'Adversaire (2026)',
    m_avg: 'Moyenne 2025',
    m_l3: 'Derniers Matchs 2025',
    def_rank: 'Rang Def Adverse (Stats 2025)',
    'Mismatch Alert': 'Indicateur'
}).sort_values(by='Moyenne 2025', ascending=False)

st.dataframe(res_df, use_container_width=True)
