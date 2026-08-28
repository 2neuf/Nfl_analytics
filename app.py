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

# --- BARRE DE FILTRES HORIZONTALE ---
st.markdown("### ⚙️ Options de filtrage")

col_week, col_game, col_crit, col_adv, col_limit = st.columns([1, 2.2, 3, 2.2, 1.4])

with col_week:
    available_weeks = sorted(schedule_2026['week'].unique())
    selected_week = st.selectbox("Semaine NFL", options=available_weeks, index=0)

# Filtrage du calendrier pour la semaine choisie
week_schedule = schedule_2026[schedule_2026['week'] == selected_week]

with col_game:
    game_options = ["Toutes les rencontres"] + [
        f"{row['away_team']} @ {row['home_team']}" for _, row in week_schedule.iterrows()
    ]
    selected_game = st.selectbox("Rencontre", options=game_options)

criterion_options = {
    "Yards à la passe concédés aux QB": ("QB", "passing"),
    "Yards à la course concédés aux QB": ("QB", "rushing"),
    "Yards à la course concédés aux RB": ("RB", "rushing"),
    "Yards à la réception concédés aux RB": ("RB", "receiving"),  
    "Yards à la réception concédés aux WR": ("WR", "receiving"),
    "Yards à la réception concédés aux TE": ("TE", "receiving")   
}

with col_crit:
    selected_criterion = st.selectbox(
        "Critère d'analyse",
        options=list(criterion_options.keys())
    )

# Extraction de la position et de la catégorie de stat
target_position, stat_category = criterion_options[selected_criterion]

# Valeur par défaut dynamique par équipe selon la position sélectionnée
default_team_limits = {
    "QB": 1,
    "RB": 2,
    "WR": 3,
    "TE": 1
}
default_limit = default_team_limits.get(target_position, 1)

with col_adv:
    filter_advantage = st.selectbox(
        "Niveau d'avantage",
        options=["Tous les avantages", "🔥 Gros avantages uniquement (OFF & DEF)"],
        index=0
    )

with col_limit:
    max_players_per_team = st.number_input(
        "Limite par équipe",
        min_value=1,
        max_value=10,
        value=default_limit,
        step=1,
        key=f"limit_team_{target_position}"
    )

st.markdown("---")

# --- PRÉPARATION DES MATCHUPS 2026 ---
home_teams = week_schedule[['home_team', 'away_team']].rename(columns={'home_team': 'team', 'away_team': 'opponent_team'})
away_teams = week_schedule[['away_team', 'home_team']].rename(columns={'away_team': 'team', 'home_team': 'opponent_team'})
matchups_2026 = pd.concat([home_teams, away_teams])

# Merge Roster & Calendrier de la semaine
df_merged = pd.merge(roster_2026, matchups_2026, on='team', how='inner')

# Filtrage par rencontre si sélectionnée
if selected_game != "Toutes les rencontres":
    away, home = selected_game.split(" @ ")
    df_merged = df_merged[df_merged['team'].isin([away, home])]

# Filtrage strict sur la position unique du critère
df_merged = df_merged[df_merged['position'] == target_position]

# --- FUSION AVEC STATS JOUEURS ---
merge_key = 'player_id' if ('player_id' in df_merged.columns and 'player_id' in players_df.columns) else 'player_name'
df_merged = pd.merge(df_merged, players_df, on=merge_key, how='left')

# Alignement du nom de colonne position après merge
if 'position_x' in df_merged.columns:
    df_merged['position'] = df_merged['position_x']

# --- FUSION AVEC DÉFENSES (PAR OPPONENT_TEAM ET POSITION) ---
df_merged = pd.merge(
    df_merged, 
    def_df, 
    on=['opponent_team', 'position'], 
    how='left'
)

# --- SÉLECTION DES COLONNES DE STATS (INCLUANT MOYENNE AJUSTÉE) ---
if stat_category == "receiving":
    m_avg, m_adj, m_l3, def_rank, def_avg = "rec_yds_avg", "rec_yds_adj", "rec_yds_l3", "rec_def_rank", "rec_yds_allowed_pg"
elif stat_category == "rushing":
    m_avg, m_adj, m_l3, def_rank, def_avg = "rush_yds_avg", "rush_yds_adj", "rush_yds_l3", "rush_def_rank", "rush_yds_allowed_pg"
else:  # passing
    m_avg, m_adj, m_l3, def_rank, def_avg = "pass_yds_avg", "pass_yds_adj", "pass_yds_l3", "pass_def_rank", "pass_yds_allowed_pg"

# --- LOGIQUE D'INDICATEUR & NIVEAU D'AVANTAGE ---
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
        # Rangs 13 à 19 (Zone neutre) : Exclus
        return None

df_merged['Mismatch Alert'] = df_merged[def_rank].apply(get_advantage_indicator)

# --- FORMATAGE ET FILTRAGE DU TABLEAU ---
res_df = df_merged.dropna(subset=[m_avg, 'Mismatch Alert']).copy()

if filter_advantage == "🔥 Gros avantages uniquement (OFF & DEF)":
    res_df = res_df[res_df['Mismatch Alert'].isin(["🔥 Gros avantage OFF", "🔒 Gros avantage DEF"])]

# Arrondi à l'entier pour toutes les colonnes numériques
for col in [m_avg, m_adj, m_l3, def_avg, def_rank]:
    res_df[col] = res_df[col].round(0).astype("Int64")

col_player_avg = f'Moy. Brut ({base_year})'
col_player_adj = f'Moy. Ajustée ({base_year})'

name_col = 'player_name_x' if 'player_name_x' in res_df.columns else 'player_name'
cols_display = [name_col, 'position', 'team', 'opponent_team', m_avg, m_adj, m_l3, def_avg, def_rank, 'Mismatch Alert']

res_df = res_df[cols_display].rename(columns={
    name_col: 'Joueur',
    'position': 'Pos',
    'team': 'Équipe',
    'opponent_team': 'Adversaire',
    m_avg: col_player_avg,
    m_adj: col_player_adj,
    m_l3: 'Derniers Matchs',
    def_avg: f'Yards Concédés/M aux {target_position}',
    def_rank: f'Rang Déf. vs {target_position} ({base_year})',
    'Mismatch Alert': 'Indicateur'
})

# --- TRI ET FILTRAGE PAR ÉQUIPE ---
# 1. Tri par la moyenne brute (décroissant)
res_df = res_df.sort_values(by=col_player_avg, ascending=False)

# 2. Limitation par équipe
res_df = res_df.groupby('Équipe').head(max_players_per_team)

# 3. Retri final sur la moyenne brute
res_df = res_df.sort_values(by=col_player_avg, ascending=False)

# 4. Réinitialisation propre de l'index (1, 2, 3...)
res_df = res_df.reset_index(drop=True)
res_df.index = res_df.index + 1

# --- AFFICHAGE TABLEAU ---
title_suffix = f" — {selected_game}" if selected_game != "Toutes les rencontres" else ""
st.subheader(f"Matchups Semaine {selected_week}{title_suffix}")
st.caption(f"🎯 **Critère sélectionné :** {selected_criterion} | Max. {max_players_per_team} {target_position} par équipe")

st.dataframe(res_df, use_container_width=True)
