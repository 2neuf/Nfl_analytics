import nfl_data_py as nfl
import pandas as pd

def load_data_for_2026_season():
    """Charge les stats de 2025 (historique) et le calendrier 2026."""
    # 1. Stats de la saison 2025 (Baseline)
    df_players_2025 = nfl.import_weekly_data([2025])
    
    # Standardisation du nom de joueur
    if 'player_name' not in df_players_2025.columns and 'player_display_name' in df_players_2025.columns:
        df_players_2025['player_name'] = df_players_2025['player_display_name']

    # 2. Calendrier de la saison 2026
    schedule_2026 = nfl.import_schedules([2026])
    
    # 3. Rosters / Effectifs 2026
    try:
        roster_2026 = nfl.import_seasonal_rosters([2026])
    except Exception:
        # Fallback si le roster complet 2026 n'est pas encore totalement mis à jour
        roster_2026 = df_players_2025[['player_id', 'player_name', 'position', 'recent_team']].drop_duplicates()
        roster_2026['status'] = 'Active'

    return df_players_2025, schedule_2026, roster_2026

def calculate_2025_player_baselines(df_players_2025):
    """Calcule les moyennes 2025 (Saison, L3, Home/Away)."""
    df_players_2025 = df_players_2025.sort_values(by=['player_id', 'week'])

    # Moyennes globales 2025
    player_stats = df_players_2025.groupby(['player_id', 'player_name', 'position']).agg(
        pass_yds_avg=('passing_yards', 'mean'),
        rush_yds_avg=('rushing_yards', 'mean'),
        rec_yds_avg=('receiving_yards', 'mean'),
    ).reset_index()

    # Calcul des 3 derniers matchs de 2025 (L3)
    df_players_2025['rec_l3'] = df_players_2025.groupby('player_id')['receiving_yards'].transform(lambda x: x.tail(3).mean())
    df_players_2025['rush_l3'] = df_players_2025.groupby('player_id')['rushing_yards'].transform(lambda x: x.tail(3).mean())
    df_players_2025['pass_l3'] = df_players_2025.groupby('player_id')['passing_yards'].transform(lambda x: x.tail(3).mean())

    l3_stats = df_players_2025.groupby('player_id').agg(
        rec_yds_l3=('rec_l3', 'last'),
        rush_yds_l3=('rush_l3', 'last'),
        pass_yds_l3=('pass_l3', 'last')
    ).reset_index()

    baselines = pd.merge(player_stats, l3_stats, on='player_id', how='left')
    return baselines

def calculate_2025_defense_rankings(df_players_2025):
    """Classement des défenses basé sur l'ensemble de la saison 2025."""
    def_stats = df_players_2025.groupby('opponent_team').agg(
        pass_yards_allowed_game=('passing_yards', lambda x: x.sum() / df_players_2025['week'].nunique()),
        rush_yards_allowed_game=('rushing_yards', lambda x: x.sum() / df_players_2025['week'].nunique())
    ).reset_index()

    # Rangs 2025 (1 = Meilleure défense, 32 = Pire défense)
    def_stats['pass_def_rank_2025'] = def_stats['pass_yards_allowed_game'].rank(ascending=True)
    def_stats['rush_def_rank_2025'] = def_stats['rush_yards_allowed_game'].rank(ascending=True)

    return def_stats
