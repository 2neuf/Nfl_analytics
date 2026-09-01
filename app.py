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
    df_base, schedule_2026, roster_2026, injuries_2026, sleeper_df, base_year = load_data_for_2026_season()
    def_pos_stats = calculate_2025_defense_by_position(df_base)
    player_baselines = calculate_2025_player_baselines(df_base, def_pos_stats)
    return player_baselines, schedule_2026, roster_2026, injuries_2026, sleeper_df, def_pos_stats, base_year

with st.spinner("Chargement des données NFL en cours..."):
    players_df, schedule_2026, roster_2026, injuries_df, sleeper_df, def_df, base_year = get_dashboard_data()

# 🔍 --- TEST DE DÉBOGAGE TEMPORAIRE ---
#st.markdown("### 🔍 Test Débogage Sleeper")
#if not sleeper_df.empty and 'player_name' in sleeper_df.columns:
 #   jacobs_debug = sleeper_df[sleeper_df['player_name'].str.contains("Jacobs", case=False, na=False)]
 #   st.write("Résultat Sleeper pour Jacobs :", jacobs_debug)
#else:
    #st.write("Le dataframe `sleeper_df` est vide ou ne contient pas la colonne `player_name`.")
# --------------------------------------


st.info(f"💡 Données de référence basées sur la saison **{base_year}**.")

# --- BARRE DE FILTRES HORIZONTALE ---
st.markdown("### ⚙️ Options de filtrage")

col_week, col_game, col_crit, col_adv, col_limit = st.columns([1, 2.2, 3, 2.2, 1.4])

with col_week:
    available_weeks = sorted(schedule_2026['week'].unique()) if 'week' in schedule_2026.columns else [1]
    selected_week = st.selectbox("Semaine NFL", options=available_weeks, index=0)

week_schedule = schedule_2026[schedule_2026['week'] == selected_week] if 'week' in schedule_2026.columns else schedule_2026

with col_game:
    if not week_schedule.empty and 'away_team' in week_schedule.columns and 'home_team' in week_schedule.columns:
        game_options = ["Toutes les rencontres"] + [
            f"{row['away_team']} @ {row['home_team']}" for _, row in week_schedule.iterrows()
        ]
    else:
        game_options = ["Toutes les rencontres"]
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
    selected_criterion = st.selectbox("Critère d'analyse", options=list(criterion_options.keys()))

target_position, stat_category = criterion_options[selected_criterion]

default_team_limits = {"QB": 1, "RB": 2, "WR": 3, "TE": 1}
default_limit = default_team_limits.get(target_position, 1)

with col_adv:
    filter_advantage = st.selectbox(
        "Niveau d'avantage",
        options=["Tous les avantages", "🔥 Gros avantages uniquement (OFF & DEF)"],
        index=0
    )

with col_limit:
    max_players_per_team = st.number_input(
        "Limite par équipe (actifs)",
        min_value=1,
        max_value=10,
        value=default_limit,
        step=1,
        key=f"limit_team_{target_position}"
    )

st.markdown("---")

# --- PRÉPARATION DES MATCHUPS 2026 ---
if not week_schedule.empty and 'home_team' in week_schedule.columns and 'away_team' in week_schedule.columns:
    home_teams = week_schedule[['home_team', 'away_team']].rename(columns={'home_team': 'team', 'away_team': 'opponent_team'})
    away_teams = week_schedule[['away_team', 'home_team']].rename(columns={'away_team': 'team', 'home_team': 'opponent_team'})
    matchups_2026 = pd.concat([home_teams, away_teams])
else:
    matchups_2026 = pd.DataFrame(columns=['team', 'opponent_team'])

df_merged = pd.merge(roster_2026, matchups_2026, on='team', how='inner') if not matchups_2026.empty else roster_2026.copy()

if selected_game != "Toutes les rencontres" and " @ " in selected_game:
    away, home = selected_game.split(" @ ")
    df_merged = df_merged[df_merged['team'].isin([away, home])]

if 'position' in df_merged.columns:
    df_merged = df_merged[df_merged['position'] == target_position]

# --- FUSION AVEC STATS JOUEURS ---
merge_key = 'player_id' if ('player_id' in df_merged.columns and 'player_id' in players_df.columns) else 'player_name'
df_merged = pd.merge(df_merged, players_df, on=merge_key, how='inner')

if 'position_x' in df_merged.columns:
    df_merged['position'] = df_merged['position_x']

# --- FUSION AVEC DÉFENSES ---
if not def_df.empty and 'opponent_team' in df_merged.columns and 'position' in df_merged.columns:
    df_merged = pd.merge(df_merged, def_df, on=['opponent_team', 'position'], how='left')

# --- FUSION AVEC RAPPORTS DE BLESSURES (SEMAINE SÉLECTIONNÉE) ---
if not injuries_df.empty and 'week' in injuries_df.columns:
    inj_week = injuries_df[injuries_df['week'] == selected_week]
    inj_key = 'player_id' if ('player_id' in df_merged.columns and 'player_id' in inj_week.columns) else 'player_name'
    
    cols_inj = [inj_key, 'report_status'] if 'report_status' in inj_week.columns else [inj_key]
    df_merged = pd.merge(df_merged, inj_week[cols_inj], on=inj_key, how='left')
else:
    df_merged['report_status'] = None

# --- FUSION AVEC SLEEPER (STATUT + ÉQUIPE TEMPS RÉEL) ---
if not sleeper_df.empty and 'sleeper_team' in sleeper_df.columns:
    if 'player_id' in df_merged.columns:
        df_merged['join_id'] = df_merged['player_id'].astype(str).str.strip()
    else:
        df_merged['join_id'] = df_merged['player_name'].astype(str).str.strip()

    if 'gsis_id' in sleeper_df.columns:
        sleeper_df['join_id'] = sleeper_df['gsis_id'].astype(str).str.strip()
    else:
        sleeper_df['join_id'] = sleeper_df['player_name'].astype(str).str.strip()

    # Fusion
    df_merged = pd.merge(df_merged, sleeper_df[['join_id', 'sleeper_status', 'sleeper_team']], on='join_id', how='left')

    # Remplacement de l'équipe si Sleeper a une info plus récente
    df_merged['team'] = df_merged['sleeper_team'].fillna(df_merged['team'])
    
    # Suppression des Free Agents / Joueurs coupés
    df_merged = df_merged[df_merged['team'].notnull() & (df_merged['team'] != "FA")]
else:
    df_merged['sleeper_status'] = None





# --- FORMATAGE DYNAMIQUE DU STATUT ---
def format_status(row):
    sleeper_stat = str(row['sleeper_status']).upper() if pd.notnull(row.get('sleeper_status')) else ""
    rep_stat = str(row['report_status']).upper() if pd.notnull(row.get('report_status')) else ""

    if sleeper_stat=="NA":
        return "🛑 NA"
        
    # Prise en compte prioritaire de Sleeper (Temps réel)
    if "DNR" in sleeper_stat or "DID NOT REPORT" in sleeper_stat:
        return "🚫 DNR"
    elif "PUP" in sleeper_stat:
        return "🏥 PUP"
    elif "SUS" in sleeper_stat:
        return "🛑 Suspendu"
    elif "IR" in sleeper_stat or "INJURED" in sleeper_stat:
        return "🏥 IR"
    elif "OUT" in sleeper_stat or "OUT" in rep_stat:
        return "🚨 Out"
    elif "DOUBTFUL" in sleeper_stat or "DOUBTFUL" in rep_stat:
        return "❌ Doubtful"
    elif "QUESTIONABLE" in sleeper_stat or "QUESTIONABLE" in rep_stat:
        return "⚠️ Questionable"
        
    return "🟢 Dispo"

df_merged['Statut'] = df_merged.apply(format_status, axis=1)


# --- SÉLECTION DES COLONNES DE STATS ---
if stat_category == "receiving":
    m_avg, m_adj, m_l3, def_rank, def_avg = "rec_yds_avg", "rec_yds_adj", "rec_yds_l3", "rec_def_rank", "rec_yds_allowed_pg"
elif stat_category == "rushing":
    m_avg, m_adj, m_l3, def_rank, def_avg = "rush_yds_avg", "rush_yds_adj", "rush_yds_l3", "rush_def_rank", "rush_yds_allowed_pg"
else:  # passing
    m_avg, m_adj, m_l3, def_rank, def_avg = "pass_yds_avg", "pass_yds_adj", "pass_yds_l3", "pass_def_rank", "pass_yds_allowed_pg"

# --- LOGIQUE D'INDICATEUR ---
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

if def_rank in df_merged.columns:
    df_merged['Mismatch Alert'] = df_merged[def_rank].apply(get_advantage_indicator)
else:
    df_merged['Mismatch Alert'] = None

# --- FORMATAGE ET FILTRAGE ---
if m_avg in df_merged.columns:
    res_df = df_merged.dropna(subset=[m_avg, 'Mismatch Alert']).copy()
else:
    res_df = pd.DataFrame()

if not res_df.empty:
    if filter_advantage == "🔥 Gros avantages uniquement (OFF & DEF)":
        res_df = res_df[res_df['Mismatch Alert'].isin(["🔥 Gros avantage OFF", "🔒 Gros avantage DEF"])]

    # Arrondi de sécurité
    for col in [m_avg, m_adj, m_l3, def_avg, def_rank]:
        if col in res_df.columns:
            res_df[col] = pd.to_numeric(res_df[col], errors='coerce').round(0).astype("Int64")

    col_player_avg = f'Moy. Brut ({base_year})'
    col_player_adj = f'Moy. Ajustée ({base_year})'
    name_col = 'player_name_x' if 'player_name_x' in res_df.columns else ('player_name' if 'player_name' in res_df.columns else 'Joueur')
    
    cols_display = [c for c in [name_col, 'position', 'Statut', 'team', 'opponent_team', m_avg, m_adj, m_l3, def_avg, def_rank, 'Mismatch Alert'] if c in res_df.columns]

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

    # --- LOGIQUE DYNAMIQUE DE CASCADE DES BLESSURES ---
sort_col = col_player_adj if col_player_adj in res_df.columns else col_player_avg

if sort_col in res_df.columns and 'Équipe' in res_df.columns:
    # 1. Tri des joueurs du meilleur au moins bon
    res_df = res_df.sort_values(by=sort_col, ascending=False)
    
    # 2. Identification des inactifs (Out, IR, PUP, NA, Exempt, etc.)
    res_df['is_inactive'] = res_df['Statut'].ne("🟢 Dispo")
    
    # 3. Compte cumulatif des joueurs DISPONIBLES uniquement (0 pour les inactifs)
    res_df['available_count'] = (~res_df['is_inactive']).astype(int)
    res_df['cum_available'] = res_df.groupby('Équipe')['available_count'].cumsum()
    
    # 4. Conservation des joueurs :
    # - Si le joueur est DISPONIBLE : on le garde si son rang de dispo <= limite (ex: <= 2)
    # - Si le joueur est INACTIF : on le garde SEULEMENT S'IL EST ARRIVÉ AVANT d'atteindre la limite de disponibles
    res_df = res_df[
        (~res_df['is_inactive'] & (res_df['cum_available'] <= max_players_per_team)) |
        (res_df['is_inactive'] & (res_df['cum_available'] < max_players_per_team))
    ]
    
    # Nettoyage des colonnes de calcul et re-tri
    res_df = res_df.drop(columns=['is_inactive', 'available_count', 'cum_available'])
    res_df = res_df.sort_values(by=sort_col, ascending=False)


    res_df = res_df.reset_index(drop=True)
    res_df.index = res_df.index + 1

    # Affichage
    title_suffix = f" — {selected_game}" if selected_game != "Toutes les rencontres" else ""
    st.subheader(f"Matchups Semaine {selected_week}{title_suffix}")
    st.caption(f"🎯 **Critère sélectionné :** {selected_criterion} | Max. {max_players_per_team} {target_position} actif(s) par équipe")

    st.dataframe(res_df, width="stretch")
else:
    st.warning("Aucune donnée ou aucun mismatch correspondant trouvé pour ce critère et ces filtres.")
