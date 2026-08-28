import pandas as pd
import streamlit as st

@st.cache_data
def load_data_for_2026_season():
    """
    Charge les jeux de données bruts nécessaires pour la saison 2026.
    Ajuste les noms de fichiers et de colonnes selon ton projet.
    """
    base_year = 2025
    
    # Remplacer par tes chargements de données réels (ex: pd.read_csv / pd.read_parquet)
    df_base = pd.read_csv(f"data/player_stats_{base_year}.csv")
    schedule_2026 = pd.read_csv("data/schedule_2026.csv")
    roster_2026 = pd.read_csv("data/roster_2026.csv")
    
    return df_base, schedule_2026, roster_2026, base_year


def calculate_2025_player_baselines(df_players_base):
    """
    Calcule les moyennes individuelles brutes et ajustées selon le niveau des défenses affrontées.
    """
    df_players_base = df_players_base.sort_values(by=['player_id', 'week']).copy()

    # --- 1. CALCUL DES MOYENNES DÉFENSIVES CONCÉDÉES PAR MATCH ---
    games_def = df_players_base.groupby('opponent_team')['week'].nunique().rename('def_games')

    def_totals = df_players_base.groupby(['opponent_team', 'position']).agg(
        pass_allowed=('passing_yards', 'sum'),
        rush_allowed=('rushing_yards', 'sum'),
        rec_allowed=('receiving_yards', 'sum')
    ).reset_index()

    def_totals = pd.merge(def_totals, games_def, on='opponent_team', how='left')
    def_totals['def_pass_pg'] = def_totals['pass_allowed'] / def_totals['def_games']
    def_totals['def_rush_pg'] = def_totals['rush_allowed'] / def_totals['def_games']
    def_totals['def_rec_pg'] = def_totals['rec_allowed'] / def_totals['def_games']

    # --- 2. CALCUL DES MOYENNES GLOBALES DE LA LIGUE PAR POSITION ---
    league_avgs = def_totals.groupby('position').agg(
        lg_pass_pg=('def_pass_pg', 'mean'),
        lg_rush_pg=('def_rush_pg', 'mean'),
        lg_rec_pg=('def_rec_pg', 'mean')
    ).reset_index()

    # --- 3. MERGE SUR LE DATASET JOUEURS PAR MATCH ---
    df_adj = pd.merge(
        df_players_base,
        def_totals[['opponent_team', 'position', 'def_pass_pg', 'def_rush_pg', 'def_rec_pg']],
        on=['opponent_team', 'position'],
        how='left'
    )
    df_adj = pd.merge(df_adj, league_avgs, on='position', how='left')

    # --- 4. CALCUL DES PERFORMANCES AJUSTÉES PAR MATCH ---
    eps = 1e-5  # Pour éviter les divisions par zéro
    df_adj['pass_factor'] = df_adj['lg_pass_pg'] / (df_adj['def_pass_pg'] + eps)
    df_adj['rush_factor'] = df_adj['lg_rush_pg'] / (df_adj['def_rush_pg'] + eps)
    df_adj['rec_factor'] = df_adj['lg_rec_pg'] / (df_adj['def_rec_pg'] + eps)

    df_adj['adj_passing_yards'] = df_adj['passing_yards'] * df_adj['pass_factor']
    df_adj['adj_rushing_yards'] = df_adj['rushing_yards'] * df_adj['rush_factor']
    df_adj['adj_receiving_yards'] = df_adj['receiving_yards'] * df_adj['rec_factor']

    # --- 5. AGRÉGATION ET MOYENNES PAR JOUEUR ---
    player_stats = df_adj.groupby(['player_id', 'player_name', 'position']).agg(
        pass_yds_avg=('passing_yards', 'mean'),
        rush_yds_avg=('rushing_yards', 'mean'),
        rec_yds_avg=('receiving_yards', 'mean'),
        pass_yds_adj=('adj_passing_yards', 'mean'),
        rush_yds_adj=('adj_rushing_yards', 'mean'),
        rec_yds_adj=('adj_receiving_yards', 'mean')
    ).reset_index()

    # --- 6. MOYENNES SUR LES 3 DERNIERS MATCHS ---
    df_adj['rec_l3'] = df_adj.groupby('player_id')['receiving_yards'].transform(lambda x: x.tail(3).mean())
    df_adj['rush_l3'] = df_adj.groupby('player_id')['rushing_yards'].transform(lambda x: x.tail(3).mean())
    df_adj['pass_l3'] = df_adj.groupby('player_id')['passing_yards'].transform(lambda x: x.tail(3).mean())

    l3_stats = df_adj.groupby('player_id').agg(
        rec_yds_l3=('rec_l3', 'last'),
        rush_yds_l3=('rush_l3', 'last'),
        pass_yds_l3=('pass_l3', 'last')
    ).reset_index()

    return pd.merge(player_stats, l3_stats, on='player_id', how='left')


def calculate_2025_defense_by_position(df_players_base):
    """
    Calcule le rang et les yards moyens concédés par chaque défense par position.
    """
    games_per_def = df_players_base.groupby('opponent_team')['week'].nunique().rename('games_played')

    def_stats = df_players_base.groupby(['opponent_team', 'position']).agg(
        pass_yds_allowed=('passing_yards', 'sum'),
        rush_yds_allowed=('rushing_yards', 'sum'),
        rec_yds_allowed=('receiving_yards', 'sum')
    ).reset_index()

    def_stats = pd.merge(def_stats, games_per_def, on='opponent_team', how='left')

    def_stats['pass_yds_allowed_pg'] = def_stats['pass_yds_allowed'] / def_stats['games_played']
    def_stats['rush_yds_allowed_pg'] = def_stats['rush_yds_allowed'] / def_stats['games_played']
    def_stats['rec_yds_allowed_pg'] = def_stats['rec_yds_allowed'] / def_stats['games_played']

    # Rangs par position (1 = défense qui concède le moins de yards)
    def_stats['pass_def_rank'] = def_stats.groupby('position')['pass_yds_allowed_pg'].rank(ascending=True)
    def_stats['rush_def_rank'] = def_stats.groupby('position')['rush_yds_allowed_pg'].rank(ascending=True)
    def_stats['rec_def_rank'] = def_stats.groupby('position')['rec_yds_allowed_pg'].rank(ascending=True)

    def_stats = def_stats.rename(columns={'opponent_team': 'opponent_team'})

    return def_stats
