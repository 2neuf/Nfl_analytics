import nflreadpy as nfl
import pandas as pd

def load_data_for_2026_season():
    try:
        df_players_base = nfl.load_player_stats(seasons=[2025], summary_level="week").to_pandas()
        df_team_stats = nfl.load_team_stats(seasons=[2025]).to_pandas()
        base_year = 2025
    except Exception:
        df_players_base = nfl.load_player_stats(seasons=[2024], summary_level="week").to_pandas()
        df_team_stats = nfl.load_team_stats(seasons=[2024]).to_pandas()
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

    # Normalisation des clés du roster
    if 'gsis_id' in roster_2026.columns:
        roster_2026['player_id'] = roster_2026['gsis_id']
    if 'team_abbr' in roster_2026.columns and 'team' not in roster_2026.columns:
        roster_2026['team'] = roster_2026['team_abbr']
    if 'full_name' in roster_2026.columns and 'player_name' not in roster_2026.columns:
        roster_2026['player_name'] = roster_2026['full_name']

    # Extraction du statut (ACT, IR, PUP, etc.)
    if 'status' in roster_2026.columns:
        roster_2026['statut'] = roster_2026['status'].fillna("ACT")
    else:
        roster_2026['statut'] = "ACT"

    # Chargement du Depth Chart
    try:
        df_depth = nfl.load_depth_charts(seasons=[2026]).to_pandas()
    except Exception:
        df_depth = nfl.load_depth_charts(seasons=[2025]).to_pandas()

    # Nettoyage et récupération de la profondeur (depth_team : 1 = RB1, 2 = RB2...)
    if 'gsis_id' in df_depth.columns:
        df_depth['player_id'] = df_depth['gsis_id']
    
    # 1. Normalisation de la colonne 'player_id' (si nécessaire)
if 'player_id' not in df_depth.columns and 'gsis_id' in df_depth.columns:
    df_depth['player_id'] = df_depth['gsis_id']

# 2. Normalisation de la colonne d'équipe (club_code / team -> depth_team)
if 'depth_team' not in df_depth.columns:
    if 'club_code' in df_depth.columns:
        df_depth['depth_team'] = df_depth['club_code']
    elif 'team' in df_depth.columns:
        df_depth['depth_team'] = df_depth['team']

# 3. Normalisation de la colonne de position ('pos' -> 'position')
if 'position' not in df_depth.columns and 'pos' in df_depth.columns:
    df_depth['position'] = df_depth['pos']

# 4. Identification de la colonne de tri
sort_col = 'week' if 'week' in df_depth.columns else ('dt' if 'dt' in df_depth.columns else df_depth.columns[0])

# 5. Groupby et agrégation sécurisés
groupby_cols = ['player_id']
if 'position' in df_depth.columns:
    groupby_cols.append('position')

df_depth_clean = (
    df_depth.sort_values(by=sort_col)
    .groupby(groupby_cols)
    .agg(depth_team=('depth_team', 'last'))
    .reset_index()
)

    # Merge du Depth Chart dans le Roster
    roster_2026 = pd.merge(roster_2026, df_depth_clean, on=['player_id', 'position'], how='left')
    roster_2026['depth_team'] = roster_2026['depth_team'].fillna(99).astype(int)

    return df_players_base, df_team_stats, schedule_2026, roster_2026, base_year


def calculate_2025_player_baselines(df_players_base):
    df_reg = df_players_base[df_players_base['week'] <= 18].copy() if 'week' in df_players_base.columns else df_players_base.copy()
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


def calculate_2025_defense_by_position(df_players_base, df_team_stats):
    df_reg = df_players_base[df_players_base['week'] <= 18].copy()

    games_per_team = df_reg.groupby('opponent_team')['week'].nunique().reset_index()
    games_per_team.rename(columns={'week': 'games_played'}, inplace=True)

    def_pos_stats = df_reg.groupby(['opponent_team', 'position']).agg(
        rec_yds_allowed=('receiving_yards', 'sum'),
        rush_yds_allowed=('rushing_yards', 'sum'),
        pass_yds_allowed=('passing_yards', 'sum')
    ).reset_index()

    def_pos_stats = pd.merge(def_pos_stats, games_per_team, on='opponent_team', how='left')

    def_pos_stats['rec_yds_allowed_pg'] = def_pos_stats['rec_yds_allowed'] / def_pos_stats['games_played']
    def_pos_stats['rush_yds_allowed_pg'] = def_pos_stats['rush_yds_allowed'] / def_pos_stats['games_played']
    def_pos_stats['pass_yds_allowed_pg'] = def_pos_stats['pass_yds_allowed'] / def_pos_stats['games_played']

    if df_team_stats is not None and 'passing_yards_against' in df_team_stats.columns:
        team_def = df_team_stats[['team', 'passing_yards_against', 'rushing_yards_against', 'games']].copy()
        team_def['official_pass_pg'] = team_def['passing_yards_against'] / team_def['games']
        team_def['official_rush_pg'] = team_def['rushing_yards_against'] / team_def['games']
        
        def_pos_stats = pd.merge(def_pos_stats, team_def, left_on='opponent_team', right_on='team', how='left')
        qb_mask = def_pos_stats['position'] == 'QB'
        def_pos_stats.loc[qb_mask, 'pass_yds_allowed_pg'] = def_pos_stats.loc[qb_mask, 'official_pass_pg']

    def_pos_stats['rec_def_rank'] = def_pos_stats.groupby('position')['rec_yds_allowed_pg'].rank(ascending=True)
    def_pos_stats['rush_def_rank'] = def_pos_stats.groupby('position')['rush_yds_allowed_pg'].rank(ascending=True)
    def_pos_stats['pass_def_rank'] = def_pos_stats.groupby('position')['pass_yds_allowed_pg'].rank(ascending=True)

    return def_pos_stats
