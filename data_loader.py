import nfl_data_py as nfl
import pandas as pd

def load_data_for_2026_season():
    """Charge les stats de référence et le calendrier 2026 avec gestion des erreurs 404."""
    
    # 1. Chargement des stats (Tente 2025, bascule sur 2024 si 404)
    try:
        df_players_base = nfl.import_weekly_data([2025])
        base_year = 2025
    except Exception:
        df_players_base = nfl.import_weekly_data([2024])
        base_year = 2024

    if 'player_name' not in df_players_base.columns and 'player_display_name' in df_players_base.columns:
        df_players_base['player_name'] = df_players_base['player_display_name']

    # 2. Chargement du calendrier 2026 (Secours sur 2025/2024 si indisponible)
    try:
        schedule_2026 = nfl.import_schedules([2026])
    except Exception:
        try:
            schedule_2026 = nfl.import_schedules([2025])
        except Exception:
            schedule_2026 = nfl.import_schedules([2024])

    # 3. Effectifs / Rosters
    try:
        roster_2026 = nfl.import_seasonal_rosters([2026])
    except Exception:
        roster_2026 = df_players_base[['player_id', 'player_name', 'position', 'recent_team']].drop_duplicates()
        roster_2026 = roster_2026.rename(columns={'recent_team': 'team'})
        roster_2026['status'] = 'Active'

    return df_players_base, schedule_2026, roster_2026, base_year

def calculate_2025_player_baselines(df_players_base):
    """Calcule les moyennes (Saison et L3)."""
    df_players_base = df_players_base.sort_values(by=['player_id', 'week'])

    player_stats = df_players_base.groupby(['player_id', 'player_name', 'position']).agg(
        pass_yds_avg=('passing_yards', 'mean'),
        rush_yds_avg=('rushing_yards', 'mean'),
        rec_yds_avg=('receiving_yards', 'mean'),
    ).reset_index()

    # Calcul des 3 derniers matchs
    df_players_base['rec_l3'] = df_players_base.groupby('player_id')['receiving_yards'].transform(lambda x: x.tail(3).mean())
    df_players_base['rush_l3'] = df_players_base.groupby('player_id')['rushing_yards'].transform(lambda x: x.tail(3).mean())
    df_players_base['pass_l3'] = df_players_base.groupby('player_id')['passing_yards'].transform(lambda x: x.tail(3).mean())

    l3_stats = df_players_base.groupby('player_id').agg(
        rec_yds_l3=('rec_l3', 'last'),
        rush_yds_l3=('rush_l3', 'last'),
        pass_yds_l3=('pass_l3', 'last')
    ).reset_index()

    return pd.merge(player_stats, l3_stats, on='player_id', how='left')

def calculate_2025_defense_rankings(df_players_base):
    """Classement des défenses (1 = Meilleure, 32 = Pire)."""
    def_stats = df_players_base.groupby('opponent_team').agg(
        pass_yards_allowed_game=('passing_yards', lambda x: x.sum() / max(df_players_base['week'].nunique(), 1)),
        rush_yards_allowed_game=('rushing_yards', lambda x: x.sum() / max(df_players_base['week'].nunique(), 1))
    ).reset_index()

    def_stats['pass_def_rank_2025'] = def_stats['pass_yards_allowed_game'].rank(ascending=True)
    def_stats['rush_def_rank_2025'] = def_stats['rush_yards_allowed_game'].rank(ascending=True)

    return def_stats
