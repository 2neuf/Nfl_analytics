import streamlit as st
import pandas as pd
from data_loader import load_data_for_2026_season, calculate_2025_player_baselines, calculate_2025_defense_rankings

st.set_page_config(page_title="NFL Mismatch Finder 2026", layout="wide")
st.title("🏈 NFL Mismatch Finder 2026")

@st.cache_data(ttl=3600)
def get_dashboard_data():
    df_base, schedule_2026, roster_2026, base_year = load_data_for_2026_season()
    player_baselines = calculate_2025_player_baselines(df_base)
    def_rankings = calculate_2025_defense_rankings(df_base)
    return player_baselines, schedule_2026, roster_2026, def_rankings, base_year

with st.spinner("Chargement des données NFL en cours..."):
    players_df, schedule_2026, roster_2026, def_df, base_year = get_dashboard_data()

st.info(f"💡 Données de référence basées sur la saison **{base_year}**.")

# Sidebar
st.sidebar.header("Paramètres 2026")
available_weeks = sorted(schedule_2026['week'].unique())
selected_week = st.sidebar.selectbox("Semaine NFL", options=available_weeks, index=0)
selected_position = st.sidebar.multiselect("Position", options=["QB", "RB", "WR", "TE"], default=["WR", "RB"])
stat_type = st.sidebar.selectbox("Pari ciblé", options=["Receiving Yards", "Rushing Yards", "Passing Yards"])

# Matchups
week_schedule = schedule_2026[schedule_2026['week'] == selected_week]
home_teams = week_schedule[['home_team', 'away_team']].rename(columns={'home_team': 'team', 'away_team': 'opponent_team'})
away_teams = week_schedule[['away_team', 'home_team']].rename(columns={'away_team': 'team', 'home_team': 'opponent_team'})
matchups_2026 = pd.concat([home_teams, away_teams])

# Merge Roster / Calendrier
df_merged = pd.merge(roster_2026, matchups_2026, on='team', how='inner')
df_merged = df_merged[df_merged['position'].isin(selected_position)]

# Fusion Stats Joueurs (Secours sur player_name si player_id absent)
merge_key = 'player_id' if ('player_id' in df_merged.columns and 'player_id' in players_df.columns) else 'player_name'
df_merged = pd.merge(df_merged, players_df, on=merge_key, how='left')

# Fusion Défenses
df_merged = pd.merge(df_merged, def_df, left_on='opponent_team', right_on='opponent_team', how='left')

if stat_type == "Receiving Yards":
    m_avg, m_l3, def_rank = "rec_yds_avg", "rec_yds_l3", "pass_def_rank_2025"
elif stat_type == "Rushing Yards":
    m_avg, m_l3, def_rank = "rush_yds_avg", "rush_yds_l3", "rush_def_rank_2025"
else:
    m_avg, m_l3, def_rank = "pass_yds_avg", "pass_yds_l3", "pass_def_rank_2025"

df_merged['Mismatch Alert'] = df_merged[def_rank].apply(
    lambda x: "🔥 TOP MISMATCH" if x >= 24 else ("⚠️ Mismatch Moyen" if x >= 16 else "OK") if pd.notnull(x) else "N/A"
)

st.subheader(f"Matchups Semaine {selected_week}")

name_col = 'player_name_x' if 'player_name_x' in df_merged.columns else 'player_name'
pos_col = 'position_x' if 'position_x' in df_merged.columns else 'position'
cols_display = [name_col, pos_col, 'team', 'opponent_team', m_avg, m_l3, def_rank, 'Mismatch Alert']

res_df = df_merged[cols_display].rename(columns={
    name_col: 'Joueur',
    pos_col: 'Pos',
    'team': 'Équipe',
    'opponent_team': 'Adversaire',
    m_avg: f'Moyenne ({base_year})',
    m_l3: 'Derniers Matchs',
    def_rank: f'Rang Def Adverse ({base_year})',
    'Mismatch Alert': 'Indicateur'
}).sort_values(by=f'Moyenne ({base_year})', ascending=False)

st.dataframe(res_df, width="stretch")
