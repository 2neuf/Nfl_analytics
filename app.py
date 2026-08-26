import streamlit as st
import pandas as pd
from data_loader import (
    load_data_for_2026_season,
    calculate_2025_player_baselines,
    calculate_2025_defense_by_position
)

st.set_page_config(page_title="NFL Mismatch Finder 2026", layout="wide")
st.title("🏈 NFL Mismatch Finder 2026")

@st.cache_data(ttl=3600)
def get_dashboard_data():
    df_base, schedule_2026, roster_2026, base_year = load_data_for_2026_season()
    player_baselines = calculate_2025_player_baselines(df_base)
    def_pos_stats = calculate_2025_defense_by_position(df_base)
    return player_baselines, schedule_2026, roster_2026, def_pos_stats, base_year

with st.spinner("Chargement des données NFL en cours..."):
    players_df, schedule_2026, roster_2026, def_df, base_year = get_dashboard_data()

st.info(f"💡 Données de référence basées sur la saison **{base_year}**.")

# --- SIDEBAR & FILTRES ---
st.sidebar.header("Paramètres 2026")

available_weeks = sorted(schedule_2026['week'].unique())
selected_week = st.sidebar.selectbox("Semaine NFL", options=available_weeks, index=0)

selected_position = st.sidebar.multiselect(
    "Positions", 
    options=["WR", "RB", "QB", "TE"], 
    default=["WR", "RB"]
)

stat_type = st.sidebar.selectbox(
    "Pari / Statistique ciblée", 
    options=["Receiving Yards", "Rushing Yards", "Passing Yards"]
)

# --- PRÉPARATION DES MATCHUPS 2026 ---
week_schedule = schedule_2026[schedule_2026['week'] == selected_week]
home_teams = week_schedule[['home_team', 'away_team']].rename(columns={'home_team': 'team', 'away_team': 'opponent_team'})
away_teams = week_schedule[['away_team', 'home_team']].rename(columns={'away_team': 'team', 'home_team': 'opponent_team'})
matchups_2026 = pd.concat([home_teams, away_teams])

# Merge Roster & Calendrier de la semaine
df_merged = pd.merge(roster_2026, matchups_2026, on='team', how='inner')

if selected_position:
    df_merged = df_merged[df_merged['position'].isin(selected_position)]

# --- FUSION AVEC STATS JOUEURS ---
merge_key = 'player_id' if ('player_id' in df_merged.columns and 'player_id' in players_df.columns) else 'player_name'
df_merged = pd.merge(df_merged, players_df, on=merge_key, how='left')

# Alignement du nom de colonne position après merge si création de suffixes
if 'position_x' in df_merged.columns:
    df_merged['position'] = df_merged['position_x']

# --- FUSION AVEC DÉFENSES (PAR OPONENT_TEAM ET POSITION) ---
df_merged = pd.merge(
    df_merged, 
    def_df, 
    on=['opponent_team', 'position'], 
    how='left'
)

# --- SÉLECTION DE LA STAT ET RANKING ---
if stat_type == "Receiving Yards":
    m_avg, m_l3, def_rank, def_avg = "rec_yds_avg", "rec_yds_l3", "rec_def_rank", "rec_yds_allowed_pg"
elif stat_type == "Rushing Yards":
    m_avg, m_l3, def_rank, def_avg = "rush_yds_avg", "rush_yds_l3", "rush_def_rank", "rush_yds_allowed_pg"
else:
    m_avg, m_l3, def_rank, def_avg = "pass_yds_avg", "pass_yds_l3", "pass_def_rank", "pass_yds_allowed_pg"

# Indicateur de matchup (32 = défense concédant le plus de yards à la position)
df_merged['Mismatch Alert'] = df_merged[def_rank].apply(
    lambda x: "🔥 TOP MISMATCH" if x >= 24 else ("⚠️ Mismatch Moyen" if x >= 16 else "OK") if pd.notnull(x) else "N/A"
)

# --- AFFICHAGE TABLEAU ---
st.subheader(f"Matchups Semaine {selected_week} — {stat_type}")

name_col = 'player_name_x' if 'player_name_x' in df_merged.columns else 'player_name'
cols_display = [name_col, 'position', 'team', 'opponent_team', m_avg, m_l3, def_avg, def_rank, 'Mismatch Alert']

# Nettoyage et formatage pour Streamlit
res_df = df_merged.dropna(subset=[m_avg]).copy()

res_df = res_df[cols_display].rename(columns={
    name_col: 'Joueur',
    'position': 'Pos',
    'team': 'Équipe',
    'opponent_team': 'Adversaire',
    m_avg: f'Moy. Joueur ({base_year})',
    m_l3: 'Derniers Matchs',
    def_avg: f'Yards Concédés/M vs {stat_type}',
    def_rank: f'Rang Déf. vs Pos ({base_year})',
    'Mismatch Alert': 'Indicateur'
}).sort_values(by=f'Moy. Joueur ({base_year})', ascending=False)

st.dataframe(res_df, use_container_width=True)
