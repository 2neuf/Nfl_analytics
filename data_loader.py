import nfl_data_py as nfl
import pandas as pd

def load_weekly_data(years=[2024]):
    """Charge les statistiques hebdomadaires des joueurs et des équipes."""
    try:
        # Tente de charger l'année demandée
        df_players = nfl.import_weekly_data(years)
        df_roster = nfl.import_rosters(years)
    except Exception:
        # Secours sur l'année précédente si l'année demandée renvoie un 404
        fallback_year = [years[0] - 1]
        df_players = nfl.import_weekly_data(fallback_year)
        df_roster = nfl.import_rosters(fallback_year)

    # Fusion des infos joueurs (position, nom complet)
    players_full = pd.merge(
        df_players,
        df_roster[['player_id', 'player_name', 'position', 'status']],
        on='player_id',
        how='left'
    )
    
    return players_full


def calculate_player_metrics(df_players):
    """Calcule les moyennes saison et Last 3 (L3) Domicile/Extérieur."""
    # Tri par joueur et par semaine
    df_players = df_players.sort_values(by=['player_id', 'week'])
    
    # Calcul des moyennes glissantes sur les 3 derniers matchs (L3)
    df_players['passing_yards_L3'] = df_players.groupby('player_id')['passing_yards'].transform(lambda x: x.rolling(3, min_periods=1).mean())
    df_players['rushing_yards_L3'] = df_players.groupby('player_id')['rushing_yards'].transform(lambda x: x.rolling(3, min_periods=1).mean())
    df_players['receiving_yards_L3'] = df_players.groupby('player_id')['receiving_yards'].transform(lambda x: x.rolling(3, min_periods=1).mean())
    
    return df_players

def calculate_defense_rankings(df_players):
    """Calcule les yards et points autorisés par chaque défense."""
    defense_stats = df_players.groupby(['opponent_team']).agg(
        pass_yards_allowed=('passing_yards', 'sum'),
        rush_yards_allowed=('rushing_yards', 'sum'),
        rec_yards_allowed=('receiving_yards', 'sum'),
        sacks_performed=('sacks', 'sum'),
        games_played=('week', 'nunique')
    ).reset_index()

    # Moyennes par match autorisées
    defense_stats['pass_yards_allowed_per_game'] = defense_stats['pass_yards_allowed'] / defense_stats['games_played']
    defense_stats['rush_yards_allowed_per_game'] = defense_stats['rush_yards_allowed'] / defense_stats['games_played']
    
    # Ranking (1 = meilleure défense, 32 = pire défense/meilleur mismatch)
    defense_stats['pass_def_rank'] = defense_stats['pass_yards_allowed_per_game'].rank(ascending=True)
    defense_stats['rush_def_rank'] = defense_stats['rush_yards_allowed_per_game'].rank(ascending=True)
    
    return defense_stats

