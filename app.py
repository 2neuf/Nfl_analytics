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

# Ratios de colonnes incluant la limite de joueurs
col_week, col_game, col_crit, col_adv, col_limit = st.columns([1, 2.2, 3, 2.2, 1.3])

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

# Valeur par défaut dynamique selon la position sélectionnée
default_player_limits = {
    "QB": 2,
    "RB": 4,
    "WR": 6,
    "TE": 2
}
default_limit = default_player_limits.get(target_position, 5)

with col_adv:
    filter_advantage = st.selectbox(
        "Niveau d'avantage",
        options=["Tous les avantages", "🔥 Gros avantages uniquement (OFF & DEF)"],
        index=0
    )

with col_limit:
    # Utilisation d'une clé dynamique pour synchroniser la valeur par défaut au changement de critère
    max_players = st.number_input(
        "Limite joueurs",
        min_value=1,
        max_value=50,
        value=default_limit,
        step=1,
        key=f"limit_{target_position}"
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

# --- SÉLECTION DES COLONNES DE STATS ---
if stat_category == "receiving":
    m_avg, m_l3, def_rank, def_avg = "rec_yds_avg", "rec_yds_l3", "rec_def_rank", "rec_yds_allowed_pg"
elif stat_category == "rushing":
    m_avg, m_l3, def_rank, def_avg = "rush_yds_avg", "rush_yds_l3", "rush_def_rank", "rush_yds_allowed_pg"
else:  # passing
    m_avg, m_l3, def_rank, def_avg = "pass_yds_avg", "pass_yds_l3", "pass_def_rank", "pass_yds_allowed_pg"

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
# 1. Conservation uniquement des joueurs avec une moyenne ET ayant un indicateur (exclut les rangs 13 à 19)
res_df = df_merged.dropna(subset=[m_avg, 'Mismatch Alert']).copy()

# 2. Application du filtre "Gros avantages uniquement" si sélectionné
if filter_advantage == "🔥 Gros avantages uniquement (OFF & DEF)":
    res_df = res_df[res_df['Mismatch Alert'].isin(["🔥 Gros avantage OFF", "🔒 Gros avantage DEF"])]

# Arrondi à l'entier pour toutes les colonnes de yards et de rang
for col in [m_avg, m_l3, def_avg, def_rank]:
    res_df[col] = res_df[col].round(0).astype("Int64")

# --- TRI DÉCROISSANT ET APPLIQUE LA LIMITE DE JOUEURS ---
col_player_avg = f'Moy. Joueur ({base_year})'

name_col = 'player_name_x' if 'player_name_x' in res_df.columns else 'player_name'
cols_display = [name_col, 'position', 'team', 'opponent_team', m_avg, m_l3, def_avg, def_rank, 'Mismatch Alert']

res_df = res_df[cols_display].rename(columns={
    name_col: 'Joueur',
    'position': 'Pos',
    'team': 'Équipe',
    'opponent_team': 'Adversaire',
    m_avg: col_player_avg,
    m_l3: 'Derniers Matchs',
    def_avg: f'Yards Concédés/M aux {target_position}',
    def_rank: f'Rang Déf. vs {target_position} ({base_year})',
    'Mismatch Alert': 'Indicateur'
})

# Tri strict du plus grand au plus petit sur la moyenne du joueur, puis tronquage selon la limite
res_df = res_df.sort_values(by=col_player_avg, ascending=False).head(max_players)

# --- AFFICHAGE TABLEAU ---
title_suffix = f" — {selected_game}" if selected_game != "Toutes les rencontres" else ""
st.subheader(f"Matchups Semaine {selected_week}{title_suffix}")
st.caption(f"🎯 **Critère sélectionné :** {selected_criterion} | Top {len(res_df)} joueur(s) affiché(s)")

st.dataframe(res_df, use_container_width=True)
