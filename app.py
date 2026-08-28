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
    df_base, df_team_stats, schedule_2026, roster_2026, base_year = load_data_for_2026_season()
    player_baselines = calculate_2025_player_baselines(df_base)
    def_pos_stats = calculate_2025_defense_by_position(df_base, df_team_stats)
    return player_baselines, schedule_2026, roster_2026, def_pos_stats, base_year

with st.spinner("Chargement des données NFL en cours..."):
    players_df, schedule_2026, roster_2026, def_df, base_year = get_dashboard_data()

st.info(f"💡 Données de référence basées sur la saison **{base_year}**.")

# --- SIDEBAR & FILTRES ---
st.sidebar.header("Paramètres 2026")

available_weeks = sorted(schedule_2026['week'].unique())
selected_week = st.sidebar.selectbox("Semaine NFL", options=available_weeks, index=0)

week_schedule = schedule_2026[schedule_2026['week'] == selected_week]

game_options = ["Toutes les rencontres"] + [
    f"{row['away_team']} @ {row['home_team']}" for _, row in week_schedule.iterrows()
]
selected_game = st.sidebar.selectbox("Rencontre", options=game_options)

criterion_options = {
    "Yards à la réception concédés aux WR": ("WR", "receiving"),
    "Yards à la réception concédés aux TE": ("TE", "receiving"),
    "Yards à la réception concédés aux RB": ("RB", "receiving"),
    "Yards à la course concédés aux QB": ("QB", "rushing"),
    "Yards à la course concédés aux RB": ("RB", "rushing"),
    "Yards à la passe concédés aux QB": ("QB", "passing")
}

selected_criterion = st.sidebar.selectbox(
    "Critère d'analyse",
    options=list(criterion_options.keys())
)

target_position, stat_category = criterion_options[selected_criterion]

# --- PRÉPARATION DES MATCHUPS ---
home_teams = week_schedule[['home_team', 'away_team']].rename(columns={'home_team': 'team', 'away_team': 'opponent_team'})
away_teams = week_schedule[['away_team', 'home_team']].rename(columns={'away_team': 'team', 'home_team': 'opponent_team'})
matchups_2026 = pd.concat([home_teams, away_teams])

df_merged = pd.merge(roster_2026, matchups_2026, on='team', how='inner')

if selected_game != "Toutes les rencontres":
    away, home = selected_game.split(" @ ")
    df_merged = df_merged[df_merged['team'].isin([away, home])]

df_merged = df_merged[df_merged['position'] == target_position]

merge_key = 'player_id' if ('player_id' in df_merged.columns and 'player_id' in players_df.columns) else 'player_name'
df_merged = pd.merge(df_merged, players_df, on=merge_key, how='left')

if 'position_x' in df_merged.columns:
    df_merged['position'] = df_merged['position_x']

df_merged = pd.merge(
    df_merged, 
    def_df, 
    on=['opponent_team', 'position'], 
    how='left'
)

if stat_category == "receiving":
    m_avg, m_l3, def_rank, def_avg = "rec_yds_avg", "rec_yds_l3", "rec_def_rank", "rec_yds_allowed_pg"
elif stat_category == "rushing":
    m_avg, m_l3, def_rank, def_avg = "rush_yds_avg", "rush_yds_l3", "rush_def_rank", "rush_yds_allowed_pg"
else:
    m_avg, m_l3, def_rank, def_avg = "pass_yds_avg", "pass_yds_l3", "pass_def_rank", "pass_yds_allowed_pg"

def get_advantage_indicator(rank):
    if pd.isnull(rank):
        return None
    elif rank >= 27:
        return "🔥 Gros avantage OFF"
    elif 20 <= rank <= 26:
        return "⚠️ Avantage OFF"
    elif 7 <= rank <= 12:
        return "🛡️ Avantage DEF"
    elif 1 <= rank <= 6:
        return "🔒 Gros avantage DEF"
    else:
        return None

df_merged['Mismatch Alert'] = df_merged[def_rank].apply(get_advantage_indicator)

# Création du libellé Depth Chart (ex: WR1, RB2)
df_merged['Chart'] = df_merged.apply(
    lambda r: f"{r['position']}{r['depth_team']}" if r['depth_team'] < 99 else f"{r['position']} (N/A)", 
    axis=1
)

# Nettoyage
res_df = df_merged.dropna(subset=[m_avg, 'Mismatch Alert']).copy()

for col in [m_avg, m_l3, def_avg, def_rank]:
    res_df[col] = res_df[col].round(0).astype("Int64")

# --- AFFICHAGE TABLEAU ---
title_suffix = f" — {selected_game}" if selected_game != "Toutes les rencontres" else ""
st.subheader(f"Matchups Semaine {selected_week}{title_suffix}")
st.caption(f"🎯 **Critère sélectionné :** {selected_criterion} *(Matchups neutres 13 à 19 masqués)*")

name_col = 'player_name_x' if 'player_name_x' in res_df.columns else 'player_name'
cols_display = [name_col, 'position', 'Chart', 'statut', 'team', 'opponent_team', m_avg, m_l3, def_avg, def_rank, 'Mismatch Alert', 'depth_team']

res_df = res_df[cols_display].rename(columns={
    name_col: 'Joueur',
    'position': 'Pos',
    'Chart': 'Rôle',
    'statut': 'Statut',
    'team': 'Équipe',
    'opponent_team': 'Adversaire',
    m_avg: f'Moy. Joueur ({base_year})',
    m_l3: 'Derniers Matchs',
    def_avg: f'Yards Concédés/M aux {target_position}',
    def_rank: f'Rang Déf. vs {target_position} ({base_year})',
    'Mismatch Alert': 'Indicateur'
})

# TRI PAR ORDRE DE DEPTH CHART (RB1 -> RB2 -> RB3)
res_df = res_df.sort_values(by='depth_team', ascending=True).drop(columns=['depth_team'])

st.dataframe(res_df, use_container_width=True)
