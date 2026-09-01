import nflreadpy as nfl
import pandas as pd
import numpy as np
import requests
import streamlit as st

@st.cache_data(ttl=900)
def fetch_sleeper_statuses():
    """Récupère les statuts temps réel des joueurs depuis l'API Sleeper."""
    url = "https://api.sleeper.app/v1/players/nfl"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # On extrait le gsis_id (ou full_name) et le statut
            records = []
            for p_id, p_info in data.items():
                gsis_id = p_info.get("gsis_id")
                full_name = p_info.get("full_name")
                injury_status = p_info.get("injury_status")
                
                records.append({
                    'gsis_id': gsis_id,
                    'player_name': full_name,
                    'sleeper_status': injury_status
                })
            return pd.DataFrame(records)
    except Exception:
        pass
    return pd.DataFrame(columns=['gsis_id', 'player_name', 'sleeper_status'])


def load_data_for_2026_season():
    """Charge les stats, rosters, calendriers, snap counts et blessures via nflreadpy."""
    try:
        df_players_base = nfl.load_player_stats(seasons=[2025], summary_level="week").to_pandas()
        base_year = 2025
    except Exception:
        df_players_base = nfl.load_player_stats(seasons=[2024], summary_level="week").to_pandas()
        base_year = 2024

    # --- FILTRAGE SAISON RÉGULIÈRE UNIQUE ---
    if 'season_type' in df_players_base.columns:
        df_players_base = df_players_base[df_players_base['season_type'] == 'REG'].copy()
    elif 'week' in df_players_base.columns:
        df_players_base = df_players_base[df_players_base['week'] <= 18].copy()

    if 'player_name' not in df_players_base.columns and 'player_display_name' in df_players_base.columns:
        df_players_base['player_name'] = df_players_base['player_display_name']

    # --- SNAP COUNTS ---
    try:
        snaps_df = nfl.load_snap_counts(seasons=[base_year]).to_pandas()
        if 'offense_pct' in snaps_df.columns:
            if 'pfr_player_id' in snaps_df.columns and 'player_id' not in snaps_df.columns:
                snaps_df['player_id'] = snaps_df['pfr_player_id']
            cols_snaps = [c for c in ['player_id', 'week', 'offense_pct'] if c in snaps_df.columns]
            df_players_base = pd.merge(df_players_base, snaps_df[cols_snaps], on=['player_id', 'week'], how='left')
            df_players_base = df_players_base[(df_players_base['offense_pct'].isnull()) | (df_players_base['offense_pct'] >= 0.20)].copy()
    except Exception:
        pass

    try:
        schedule_2026 = nfl.load_schedules(seasons=[2026]).to_pandas()
    except Exception:
        schedule_2026 = nfl.load_schedules(seasons=[2025]).to_pandas()

    try:
        roster_2026 = nfl.load_rosters(seasons=[2026]).to_pandas()
    except Exception:
        roster_2026 = nfl.load_rosters(seasons=[2025]).to_pandas()

    if 'gsis_id' in roster_2026.columns:
        roster_2026['player_id'] = roster_2026['gsis_id']
    if 'team_abbr' in roster_2026.columns and 'team' not in roster_2026.columns:
        roster_2026['team'] = roster_2026['team_abbr']
    if 'full_name' in roster_2026.columns and 'player_name' not in roster_2026.columns:
        roster_2026['player_name'] = roster_2026['full_name']

    # --- CHARGEMENT DES BLESSURES ---
    try:
        injuries_2026 = nfl.load_injuries(seasons=[2026]).to_pandas()
        if 'gsis_id' in injuries_2026.columns and 'player_id' not in injuries_2026.columns:
            injuries_2026['player_id'] = injuries_2026['gsis_id']
    except Exception:
        injuries_2026 = pd.DataFrame()

    sleeper_injuries=fetch_sleeper_statuses()
    
    return df_players_base, schedule_2026, roster_2026, injuries_2026, sleeper_injuries, base_year


def calculate_2025_player_baselines(df_players_base, def_pos_stats):
    """Calcule les moyennes brutes ET les moyennes ajustées par la difficulté des défenses."""
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

    base_merged = pd.merge(player_stats, l3_stats, on='player_id', how='left')

    if def_pos_stats is not None and not def_pos_stats.empty and 'opponent_team' in df_players_base.columns:
        league_pos_avg = def_pos_stats.groupby('position').agg(
            league_pass_avg=('pass_yds_allowed_pg', 'mean'),
            league_rush_avg=('rush_yds_allowed_pg', 'mean'),
            league_rec_avg=('rec_yds_allowed_pg', 'mean')
        ).reset_index()

        df_adj = df_players_base.merge(
            def_pos_stats[['opponent_team', 'position', 'pass_yds_allowed_pg', 'rush_yds_allowed_pg', 'rec_yds_allowed_pg']],
            on=['opponent_team', 'position'],
            how='left'
        ).merge(league_pos_avg, on='position', how='left')

        df_adj['pass_factor'] = (df_adj['league_pass_avg'] / df_adj['pass_yds_allowed_pg']).fillna(1.0)
        df_adj['rush_factor'] = (df_adj['league_rush_avg'] / df_adj['rush_yds_allowed_pg']).fillna(1.0)
        df_adj['rec_factor'] = (df_adj['league_rec_avg'] / df_adj['rec_yds_allowed_pg']).fillna(1.0)

        for col in ['pass_factor','rush_factor','rec_factor']:
            df_adj[col] = df_adj[col].replace([np.inf,-np.inf],1.0)
            

        df_adj['pass_yds_adj_match'] = df_adj['passing_yards'] * df_adj['pass_factor']
        df_adj['rush_yds_adj_match'] = df_adj['rushing_yards'] * df_adj['rush_factor']
        df_adj['rec_yds_adj_match'] = df_adj['receiving_yards'] * df_adj['rec_factor']

        adj_stats = df_adj.groupby('player_id').agg(
            pass_yds_adj=('pass_yds_adj_match', 'mean'),
            rush_yds_adj=('rush_yds_adj_match', 'mean'),
            rec_yds_adj=('rec_yds_adj_match', 'mean')
        ).reset_index()

        return pd.merge(base_merged, adj_stats, on='player_id', how='left')

    return base_merged


def calculate_2025_defense_by_position(df_players_base):
    """Calcule les stats et rankings défensifs de saison régulière par équipe ET par position."""
    if 'opponent_team' not in df_players_base.columns or df_players_base.empty:
        return pd.DataFrame()

    games_per_team = (
        df_players_base.groupby('opponent_team')['week']
        .nunique()
        .reset_index()
        .rename(columns={'week': 'games_played'})
    )

    def_pos_stats = df_players_base.groupby(['opponent_team', 'position']).agg(
        rec_yds_allowed=('receiving_yards', 'sum'),
        rush_yds_allowed=('rushing_yards', 'sum'),
        pass_yds_allowed=('passing_yards', 'sum')
    ).reset_index()

    def_pos_stats = pd.merge(def_pos_stats, games_per_team, on='opponent_team', how='left')

    def_pos_stats['rec_yds_allowed_pg'] = def_pos_stats['rec_yds_allowed'] / def_pos_stats['games_played']
    def_pos_stats['rush_yds_allowed_pg'] = def_pos_stats['rush_yds_allowed'] / def_pos_stats['games_played']
    def_pos_stats['pass_yds_allowed_pg'] = def_pos_stats['pass_yds_allowed'] / def_pos_stats['games_played']

    def_pos_stats['rec_def_rank'] = def_pos_stats.groupby('position')['rec_yds_allowed_pg'].rank(ascending=True)
    def_pos_stats['rush_def_rank'] = def_pos_stats.groupby('position')['rush_yds_allowed_pg'].rank(ascending=True)
    def_pos_stats['pass_def_rank'] = def_pos_stats.groupby('position')['pass_yds_allowed_pg'].rank(ascending=True)

    return def_pos_stats
