import nfl_data_py as nfl
import pandas as pd

def load_weekly_data(years=[2024]):
    """Charge les statistiques hebdomadaires des joueurs."""
    try:
        df_players = nfl.import_weekly_data(years)
    except Exception:
        fallback_year = [years[0] - 1]
        df_players = nfl.import_weekly_data(fallback_year)

    # Si la colonne player_name n'existe pas directement, on adapte
    if 'player_name' not in df_players.columns and 'player_display_name' in df_players.columns:
        df_players['player_name'] = df_players['player_display_name']

    # Statut par défaut si la colonne status n'est pas présente dans les weekly stats
    if 'status' not in df_players.columns:
        df_players['status'] = 'Active'

    return df_players

def calculate_player_metrics(df_players):
    """Calcule les moyennes saison et Last 3 (L3)."""
    df_players = df_players.sort_values(by=['player_id', 'week'])

    df_players['passing_yards_L3'] = df_players.groupby('player_id')['passing_yards'].transform(lambda x: x.rolling(3, min_periods=1).mean())
    df_players['rushing_yards_L3'] = df_players.groupby('player_id')['rushing_yards'].transform(lambda x: x.rolling(3, min_periods=1).mean())
    df_players['receiving_yards_L3'] = df_players.groupby('player_id')['receiving_yards'].transform(lambda x: x.rolling(3, min_periods=1).mean())

    return df_players

def calculate_defense_rankings(df_players):
    """Calcule les yards autorisés par chaque défense."""
    defense_stats = df_players.groupby(['opponent_team']).agg(
        pass_yards_allowed=('passing_yards', 'sum'),
        rush_yards_allowed=('rushing_yards', 'sum'),
        rec_yards_allowed=('receiving_yards', 'sum'),
        games_played=('week', 'nunique')
    ).reset_index()

    defense_stats['pass_yards_allowed_per_game'] = defense_stats['pass_yards_allowed'] / defense_stats['games_played']
    defense_stats['rush_yards_allowed_per_game'] = defense_stats['rush_yards_allowed'] / defense_stats['games_played']

    defense_stats['pass_def_rank'] = defense_stats['pass_yards_allowed_per_game'].rank(ascending=True)
    defense_stats['rush_def_rank'] = defense_stats['rush_yards_allowed_per_game'].rank(ascending=True)

    return defense_stats
