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
    df_base, df_team_stats, schedule_2026, roster_2026, base_year = load_data_for_2026_season()
    player_baselines = calculate_2025_player_baselines(df_base)
    def_pos_stats = calculate_2025_defense_by_position(df_base, df_team_stats)
    return player_baselines, schedule_2026, roster_2026, def_pos_stats, base_year

with st.spinner("Chargement des données NFL en cours..."):
    players_df, schedule_2026, roster_2026, def_df, base_year = get_dashboard_data()

st.info(f"💡 Données de référence basées sur la saison **{base_year}**")

st.title("🏈 NFL Analytics & Projections")

# --- Barre latérale de filtres ---
st.sidebar.header("Filtres")

positions_dispo = ["ALL", "QB", "RB", "WR", "TE"]
pos_filter = st.sidebar.selectbox("Position", positions_dispo)

stat_type = st.sidebar.selectbox("Statistique ciblée", ["Pass Yds", "Rush Yds", "Rec Yds"])

# Mapping des colonnes selon la stat sélectionnée
stat_map = {
    "Pass Yds": ("pass_yds_avg", "pass_yds_adj", "pass_yds_l3", "pass_yds_def_avg", "pass_yds_def_rank"),
    "Rush Yds": ("rush_yds_avg", "rush_yds_adj", "rush_yds_l3", "rush_yds_def_avg", "rush_yds_def_rank"),
    "Rec Yds":  ("rec_yds_avg",  "rec_yds_adj",  "rec_yds_l3",  "rec_yds_def_avg",  "rec_yds_def_rank")
}

m_avg, m_adj, m_l3, def_avg, def_rank = stat_map.get(stat_type, stat_map["Pass Yds"])

# --- Filtrage des joueurs ---
res_df = players_df.copy() if players_df is not None and not players_df.empty else pd.DataFrame()

if not res_df.empty:
    if pos_filter != "ALL" and "position" in res_df.columns:
        res_df = res_df[res_df["position"] == pos_filter]

    # --- Matchups et croisement défense ---
    if def_df is not None and not def_df.empty and "opponent" in res_df.columns:
        res_df = res_df.merge(def_df, on=["opponent", "position"], how="left")

    # --- CORRECTION DU CRASH (Ligne 153-154) ---
    # On vérifie si chaque colonne existe bien avant de la convertir/arrondir
    for col in [m_avg, m_adj, m_l3, def_avg, def_rank]:
        if col in res_df.columns:
            res_df[col] = pd.to_numeric(res_df[col], errors="coerce").round(0).astype("Int64")

    # Renommage des colonnes pour l'affichage final
    rename_dict = {}
    if m_avg in res_df.columns: rename_dict[m_avg] = f"Moy. Brut ({base_year})"
    if m_adj in res_df.columns: rename_dict[m_adj] = f"Moy. Ajustée ({base_year})"
    if m_l3 in res_df.columns: rename_dict[m_l3] = "Moy. 3 Derniers Matchs"
    if def_avg in res_df.columns: rename_dict[def_avg] = "Déf. Concéder"
    if def_rank in res_df.columns: rename_dict[def_rank] = "Rang Défense"

    display_df = res_df.rename(columns=rename_dict)

    # Affichage du tableau principal
    st.subheader(f"Analyses {stat_type} - Position : {pos_filter}")
    st.dataframe(display_df, use_container_width=True)

else:
    st.warning("Aucune donnée disponible à afficher.")
