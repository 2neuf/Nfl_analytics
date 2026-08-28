import pandas as pd
import nfl_data_py as nfl

def load_data_for_2026_season():
    """
    Charge les données NFL nécessaires pour la saison.
    Retourne 5 éléments pour aligner la signature de la fonction.
    """
    # 1. Détermination de l'année de référence (dernière saison complète)
    base_year = 2025

    # 2. Chargement des baselines et stats d'équipes
    try:
        df_base = nfl.import_weekly_data([base_year])
    except Exception:
        df_base = pd.DataFrame()

    try:
        df_team_stats = nfl.import_team_desc()
    except Exception:
        df_team_stats = pd.DataFrame()

    try:
        schedule_2026 = nfl.import_schedules([2026])
    except Exception:
        schedule_2026 = pd.DataFrame()

    try:
        roster_2026 = nfl.import_seasonal_rosters([2026])
    except Exception:
        roster_2026 = pd.DataFrame()

    # 3. Traitement sécurisé des Depth Charts
    try:
        df_depth = nfl.import_depth_charts([base_year])
        if df_depth is not None and not df_depth.empty:
            if 'gsis_id' in df_depth.columns and 'player_id' not in df_depth.columns:
                df_depth['player_id'] = df_depth['gsis_id']

            # Détection dynamique de la colonne de tri (évite le KeyError: 'week')
            sort_col = None
            for col_candidate in ['week', 'dt', 'game_date']:
                if col_candidate in df_depth.columns:
                    sort_col = col_candidate
                    break

            if sort_col:
                df_depth_clean = (
                    df_depth.sort_values(by=sort_col)
                    .groupby('player_id', as_index=False)
                    .agg({'depth_team': 'last'})
                )
            else:
                df_depth_clean = (
                    df_depth.groupby('player_id', as_index=False)
                    .agg({'depth_team': 'last'})
                )
        else:
            df_depth_clean = pd.DataFrame(columns=['player_id', 'depth_team'])
    except Exception:
        df_depth_clean = pd.DataFrame(columns=['player_id', 'depth_team'])

    # Injection du depth_team dans la baseline si possible
    if not df_base.empty and not df_depth_clean.empty and 'player_id' in df_base.columns:
        df_base = df_base.merge(df_depth_clean, on='player_id', how='left')

    return df_base, df_team_stats, schedule_2026, roster_2026, base_year


def calculate_2025_player_baselines(df_base):
    """Calcul des baselines joueurs sur la saison écoulée."""
    if df_base.empty:
        return pd.DataFrame()
    return df_base


def calculate_2025_defense_by_position(df_base, df_team_stats):
    """Calcul des métriques défensives concédées par position."""
    if df_base.empty:
        return pd.DataFrame()
    return df_base
