import nflreadpy as nfl
import pandas as pd

def load_data_for_2026_season():
    """Charge les données via nflreadpy et harmonise les identifiants."""
    try:
        df_players_base = nfl.load_player_stats(seasons=[2025], summary_level="week").to_pandas()
        base_year = 2025
    except Exception:
        df_players_base = nfl.load_player_stats(seasons=[2024], summary_level="week").to_pandas()
        base_year = 2024

    # Harmonisation nom du joueur
    if 'player_name' not in df_players_base.columns and 'player_display_name' in df_players_base.columns:
        df_players_base['player_name'] = df_players_base['player_display_name']

    # Calendrier
    try:
        schedule_2026 = nfl.load_schedules(seasons=[2026]).to_pandas()
    except Exception:
        schedule_2026 = nfl.load_schedules(seasons=[2025]).to_pandas()

    # Rosters (Renommage explicite de gsis_id -> player_id)
    try:
        roster_2026 = nfl.load_rosters(seasons=[2026]).to_pandas()
    except Exception:
        roster_2026 = nfl.load_rosters(seasons=[2025]).to_pandas()

    # Alignement du nom de la colonne d'identifiant dans le roster
    if 'gsis_id' in roster_2026.columns and 'player_id' not in roster_2026.columns:
        roster_2026 = roster_2026.rename(columns={'gsis_id': 'player_id'})

    return df_players_base, schedule_2026, roster_2026, base_year

def calculate_2025_player_baselines(df_players_base):
    """Calcule les moyennes (Saison et L3)."""
    df_players_base = df_players_base.sort_values(by=['player_id', 'week'])

    player_stats = df_players_base.groupby(['player_id', 'player_name', 'position']).agg(
        pass_yds_avg=('passing_yards', 'mean'),
        rush_yds_avg=('rushing_yards', 'mean'),
        rec_yds_avg=('receiving_yards', 'mean'),
    ).reset_index()

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
    """Classement des défenses."""
    def_stats = df_players_base.groupby('opponent_team').agg(
        pass_yards_allowed_game=('passing_yards', lambda x: x.sum() / max(df_players_base['week'].nunique(), 1)),
        rush_yards_allowed_game=('rushing_yards', lambda x: x.sum() / max(df_players_base['week'].nunique(), 1))
    ).reset_index()

    def_stats['pass_def_rank_2025'] = def_stats['pass_yards_allowed_game'].rank(ascending=True)
    def_stats['rush_def_rank_2025'] = def_stats['rush_yards_allowed_game'].rank(ascending=True)

    return def_stats
