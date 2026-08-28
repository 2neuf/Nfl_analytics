import streamlit as st
import pandas as pd
from data_loader import (
    load_data_for_2026_season,
    calculate_2025_player_baselines,
    calculate_2025_defense_by_position
)

st.set_page_config(page_title="NFL Analytics 2026", layout="wide")

@st.cache_data(ttl=3600)
def get_dashboard_data():
    # Dépaquetage strict des 5 valeurs renvoyées par data_loader
    df_base, df_team_stats, schedule_2026, roster_2026, base_year = load_data_for_2026_season()
    player_baselines = calculate_2025_player_baselines(df_base)
    def_pos_stats = calculate_2025_defense_by_position(df_base, df_team_stats)
    return player_baselines, schedule_2026, roster_2026, def_pos_stats, base_year


with st.spinner("Chargement des données NFL en cours..."):
    players_df, schedule_2026, roster_2026, def_df, base_year = get_dashboard_data()

st.info(f"💡 Données de référence basées sur la saison **{base_year}**")

# --- Interface / Filtres ---
st.title("🏈 NFL Analytics & Projections")

stat_type = st.selectbox("Sélectionner la statistique", ["Pass Yds", "Rush Yds", "Rec Yds"])

# Cartographie dynamique des colonnes selon le filtre
stat_prefix = stat_type.lower().replace(" ", "_")
m_avg = f"{stat_prefix}_avg" if f"{stat_prefix}_avg" in players_df.columns else "passing_yards"
m_adj = f"{stat_prefix}_adj"
m_l3 = f"{stat_prefix}_l3"
def_avg = "def_avg"
def_rank = "def_rank"

# Simulation de res_df (à adapter selon ta logique d'agrégation)
res_df = players_df.copy() if not players_df.empty else pd.DataFrame()

# --- Affichage & Formatting sécurisé ---
if res_df is not None and not res_df.empty:
    
    # Sécurisation : Arrondi exécuté uniquement sur les colonnes réellement présentes
    cols_to_round = [m_avg, m_adj, m_l3, def_avg, def_rank]
    for col in cols_to_round:
        if col in res_df.columns:
            res_df[col] = pd.to_numeric(res_df[col], errors='coerce').round(0).astype("Int64")

    col_player_avg = f'Moy. Brut ({base_year})'
    col_player_adj = f'Moy. Ajustée ({base_year})'

    st.subheader(f"Analyses et projections - {stat_type}")
    
    # Remplacement de use_container_width par width="stretch" (Norme Streamlit 2026)
    st.dataframe(res_df, width="stretch")
else:
    st.warning("Aucune donnée disponible à afficher.")
