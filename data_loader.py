import nflreadpy as nfl
import pandas as pd

def load_data_for_2026_season():
    """Charge les données via nflreadpy et garantit l'alignement des clés."""
    try:
        df_players_base = nfl.load_player_stats(seasons=[2025], summary_level="week").to_pandas()
        base_year = 2025
    except Exception:
        df_players_base = nfl.load_player_stats(seasons=[2024], summary_level="week").to_pandas()
        base_year = 2024

    if 'player_name' not in df_players_base.columns and 'player_display_name' in df_players_base.columns:
        df_players_base['player_name'] = df_players_base['player_display_name']

    try:
        schedule_2026 = nfl.load_schedules(seasons=[2026]).to_pandas()
    except Exception:
        schedule_2026 = nfl.load_schedules(seasons=[2025]).to_pandas()

    try:
        roster_2026 = nfl.load_rosters(seasons=[2026]).to_pandas()
    except Exception:
        roster_2026 = nfl.load_rosters(seasons=[2025]).to_pandas()

    # Normalisation des colonnes clés
    if 'gsis_id' in roster_2026.columns:
        roster_2026['player_id'] = roster_2026['gsis_id']
    if 'team_abbr' in roster_2026.columns and 'team' not in roster_2026.columns:
        roster_2026['team'] = roster_2026['team_abbr']
    if 'full_name' in roster_2026.columns and 'player_name' not in roster_2026.columns:
        roster_2026['player_name'] = roster_2026['full_name']

    return df_players_base, schedule_2026, roster_2026, base_year


def calculate_2025_player_baselines(df_players_base):
    """Calcule les moyennes individuelles des joueurs (saison régulière)."""
    # Restriction à la saison régulière (Semaines 1 à 18)
    if 'season_type' in df_players_base.columns:
        df_reg = df_players_base[df_players_base['season_type'] == 'REG'].copy()
    else:
        df_reg = df_players_base[df_players_base['week'] <= 18].copy()

    df_reg = df_reg.sort_values(by=['player_id', 'week'])

    player_stats = df_reg.groupby(['player_id', 'player_name', 'position']).agg(
        pass_yds_avg=('passing_yards', 'mean'),
        rush_yds_avg=('rushing_yards', 'mean'),
        rec_yds_avg=('receiving_yards', 'mean'),
    ).reset_index()

    df_reg['rec_l3'] = df_reg.groupby('player_id')['receiving_yards'].transform(lambda x: x.tail(3).mean())
    df_reg['rush_l3'] = df_reg.groupby('player_id')['rushing_yards'].transform(lambda x: x.tail(3).mean())
    df_reg['pass_l3'] = df_reg.groupby('player_id')['passing_yards'].transform(lambda x: x.tail(3).mean())

    l3_stats = df_reg.groupby('player_id').agg(
        rec_yds_l3=('rec_l3', 'last'),
        rush_yds_l3=('rush_l3', 'last'),
        pass_yds_l3=('pass_l3', 'last')
    ).reset_index()

    return pd.merge(player_stats, l3_stats, on='player_id', how='left')


def calculate_2025_defense_by_position(df_players_base):
    """
    Calcule les stats et rankings défensifs 2025 sur les 18 semaines de saison régulière
    en divisant par le nombre réel de matchs joués (17 matchs par équipe).
    """
    # 1. Filtre strict Saison Régulière (Semaines 1 à 18 incluses, hors playoffs)
    if 'season_type' in df_players_base.columns:
        df_reg = df_players_base[df_players_base['season_type'] == 'REG'].copy()
    else:
        df_reg = df_players_base[df_players_base['week'] <= 18].copy()

    # 2. Nombre réel de matchs joués par l'équipe (17 matchs)
    games_per_team = df_reg.groupby('opponent_team')['week'].nunique().reset_index()
    games_per_team.rename(columns={'week': 'games_played'}, inplace=True)

    # 3. Agrégation des yards concédés par défense et par position
    def_pos_stats = df_reg.groupby(['opponent_team', 'position']).agg(
        rec_yds_allowed=('receiving_yards', 'sum'),
        rush_yds_allowed=('rushing_yards', 'sum'),
        pass_yds_allowed=('passing_yards', 'sum')
    ).reset_index()

    # Alignement du nombre de matchs joués
    def_pos_stats = pd.merge(def_pos_stats, games_per_team, on='opponent_team', how='left')

    # 4. Calcul des moyennes concédées par match réels
    def_pos_stats['rec_yds_allowed_pg'] = def_pos_stats['rec_yds_allowed'] / def_pos_stats['games_played']
    def_pos_stats['rush_yds_allowed_pg'] = def_pos_stats['rush_yds_allowed'] / def_pos_stats['games_played']
    def_pos_stats['pass_yds_allowed_pg'] = def_pos_stats['pass_yds_allowed'] / def_pos_stats['games_played']

    # 5. Ranking au sein de chaque position (1 = défense la plus stricte, 32 = défense la plus permissive)
    def_pos_stats['rec_def_rank'] = def_pos_stats.groupby('position')['rec_yds_allowed_pg'].rank(ascending=True)
    def_pos_stats['rush_def_rank'] = def_pos_stats.groupby('position')['rush_yds_allowed_pg'].rank(ascending=True)
    def_pos_stats['pass_def_rank'] = def_pos_stats.groupby('position')['pass_yds_allowed_pg'].rank(ascending=True)

    return def_pos_stats
