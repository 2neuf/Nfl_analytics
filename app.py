import streamlit as st
import pandas as pd
from datetime import datetime
from data_loader import (
    load_data_for_2026_season,
    calculate_2025_player_baselines,
    calculate_2025_defense_by_position,
    calculate_2026_player_baselines,
    calculate_2026_defense_by_position,
    calculate_team_scoring_stats,
    get_current_nfl_week
)

st.set_page_config(page_title="NFL Mismatch Finder 2026", layout="wide")
st.title("🏈 NFL Mismatch Finder 2026")

@st.cache_data(ttl=3600)
def get_dashboard_data():
    df_base, schedule_2026, roster_2026, injuries_2026, sleeper_df, df_players_2026, depth_charts, base_year = load_data_for_2026_season()
    def_pos_stats = calculate_2025_defense_by_position(df_base)
    player_baselines = calculate_2025_player_baselines(df_base, def_pos_stats)
    
    player_2026_stats = calculate_2026_player_baselines(df_players_2026)
    def_2026_stats = calculate_2026_defense_by_position(df_players_2026)
    
    team_scoring_2025, team_scoring_2026 = calculate_team_scoring_stats()
    
    return player_baselines, schedule_2026, roster_2026, injuries_2026, sleeper_df, def_pos_stats, player_2026_stats, def_2026_stats, depth_charts, base_year, team_scoring_2025, team_scoring_2026

with st.spinner("Chargement des données NFL en cours..."):
    players_df, schedule_2026, roster_2026, injuries_df, sleeper_df, def_df, players_2026_df, def_2026_df, depth_charts, base_year, team_scoring_2025, team_scoring_2026 = get_dashboard_data()

current_week = get_current_nfl_week(schedule_2026)

st.info(f"💡 Données de référence : saison **{base_year}** | 📅 **Semaine NFL courante (auto-détectée) : Semaine {current_week}**")

tab_players, tab_teams, tab_injuries = st.tabs(["🏃 Mismatch Joueurs", "🏈 Mismatch Scoring Équipes", "🏥 Infirmerie & Profondeur"])

# ==============================================================================
# TAB 1: MISMATCH JOUEURS
# ==============================================================================
with tab_players:
    st.markdown("### ⚙️ Options de filtrage (Joueurs)")

    col_game, col_crit, col_adv, col_limit = st.columns([2.5, 3, 2.2, 1.4])

    week_schedule = schedule_2026[schedule_2026['week'] == current_week] if 'week' in schedule_2026.columns else schedule_2026

    with col_game:
        if not week_schedule.empty and 'away_team' in week_schedule.columns and 'home_team' in week_schedule.columns:
            game_options = ["Toutes les rencontres"] + [
                f"{row['away_team']} @ {row['home_team']}" for _, row in week_schedule.iterrows()
            ]
        else:
            game_options = ["Toutes les rencontres"]
        selected_game = st.selectbox("Rencontre", options=game_options, key="game_players")

    criterion_options = {
        "Yards à la passe concédés aux QB": ("QB", "passing"),
        "Yards à la course concédés aux QB": ("QB", "rushing"),
        "Yards à la course concédés aux RB": ("RB", "rushing"),
        "Yards à la réception concédés aux RB": ("RB", "receiving"),  
        "Yards à la réception concédés aux WR": ("WR", "receiving"),
        "Yards à la réception concédés aux TE": ("TE", "receiving")   
    }

    with col_crit:
        selected_criterion = st.selectbox("Critère d'analyse", options=list(criterion_options.keys()))

    target_position, stat_category = criterion_options[selected_criterion]
    default_limit = {"QB": 1, "RB": 2, "WR": 3, "TE": 1}.get(target_position, 1)

    with col_adv:
        filter_advantage = st.selectbox(
            "Niveau d'avantage",
            options=["Tous les avantages", "🔥 Gros avantages uniquement (OFF & DEF)"],
            index=0
        )

    with col_limit:
        max_players_per_team = st.number_input(
            "Limite par équipe (actifs)",
            min_value=1,
            max_value=10,
            value=default_limit,
            step=1,
            key=f"limit_team_{target_position}"
        )

    st.markdown("---")

    if not week_schedule.empty and 'home_team' in week_schedule.columns and 'away_team' in week_schedule.columns:
        home_teams = week_schedule[['home_team', 'away_team']].rename(columns={'home_team': 'team', 'away_team': 'opponent_team'})
        away_teams = week_schedule[['away_team', 'home_team']].rename(columns={'away_team': 'team', 'home_team': 'opponent_team'})
        matchups_2026 = pd.concat([home_teams, away_teams])
    else:
        matchups_2026 = pd.DataFrame(columns=['team', 'opponent_team'])

    df_merged = pd.merge(roster_2026, matchups_2026, on='team', how='inner') if not matchups_2026.empty else roster_2026.copy()

    if selected_game != "Toutes les rencontres" and " @ " in selected_game:
        away, home = selected_game.split(" @ ")
        df_merged = df_merged[df_merged['team'].isin([away, home])]

    if 'position' in df_merged.columns:
        df_merged = df_merged[df_merged['position'] == target_position]

    merge_key = 'player_id' if ('player_id' in df_merged.columns and 'player_id' in players_df.columns) else 'player_name'
    df_merged = pd.merge(df_merged, players_df, on=merge_key, how='inner')

    if 'position_x' in df_merged.columns:
        df_merged['position'] = df_merged['position_x']

    if not def_df.empty and 'opponent_team' in df_merged.columns and 'position' in df_merged.columns:
        df_merged = pd.merge(df_merged, def_df, on=['opponent_team', 'position'], how='left')

    if stat_category == "receiving":
        m_avg, m_adj, m_l3, def_rank, def_avg = "rec_yds_avg", "rec_yds_adj", "rec_yds_l3", "rec_def_rank", "rec_yds_allowed_pg"
        p_2026_avg, def_2026_avg, def_2026_rank = "rec_yds_avg_2026", "rec_yds_allowed_pg_2026", "rec_def_rank_2026"
    elif stat_category == "rushing":
        m_avg, m_adj, m_l3, def_rank, def_avg = "rush_yds_avg", "rush_yds_adj", "rush_yds_l3", "rush_def_rank", "rush_yds_allowed_pg"
        p_2026_avg, def_2026_avg, def_2026_rank = "rush_yds_avg_2026", "rush_yds_allowed_pg_2026", "rush_def_rank_2026"
    else:
        m_avg, m_adj, m_l3, def_rank, def_avg = "pass_yds_avg", "pass_yds_adj", "pass_yds_l3", "pass_def_rank", "pass_yds_allowed_pg"
        p_2026_avg, def_2026_avg, def_2026_rank = "pass_yds_avg_2026", "pass_yds_allowed_pg_2026", "pass_def_rank_2026"

    if not players_2026_df.empty and 'player_id' in df_merged.columns:
        df_merged = pd.merge(df_merged, players_2026_df[['player_id', 'games_played_2026', p_2026_avg]], on='player_id', how='left')
    else:
        df_merged['games_played_2026'] = None
        df_merged[p_2026_avg] = None

    if not def_2026_df.empty and 'opponent_team' in df_merged.columns and 'position' in df_merged.columns:
        df_merged = pd.merge(df_merged, def_2026_df[['opponent_team', 'position', def_2026_avg, def_2026_rank]], on=['opponent_team', 'position'], how='left')
    else:
        df_merged[def_2026_avg] = None
        df_merged[def_2026_rank] = None

    if not injuries_df.empty and 'week' in injuries_df.columns:
        inj_week = injuries_df[injuries_df['week'] == current_week]
        inj_key = 'player_id' if ('player_id' in df_merged.columns and 'player_id' in inj_week.columns) else 'player_name'
        cols_inj = [inj_key, 'report_status'] if 'report_status' in inj_week.columns else [inj_key]
        df_merged = pd.merge(df_merged, inj_week[cols_inj], on=inj_key, how='left')
    else:
        df_merged['report_status'] = None

    if not sleeper_df.empty and 'sleeper_team' in sleeper_df.columns:
        if 'player_id' in df_merged.columns:
            df_merged['join_id'] = df_merged['player_id'].astype(str).str.strip()
        else:
            df_merged['join_id'] = df_merged['player_name'].astype(str).str.strip()

        if 'gsis_id' in sleeper_df.columns:
            sleeper_df['join_id'] = sleeper_df['gsis_id'].astype(str).str.strip()
        else:
            sleeper_df['join_id'] = sleeper_df['player_name'].astype(str).str.strip()

        df_merged = pd.merge(df_merged, sleeper_df[['join_id', 'sleeper_status', 'sleeper_team']], on='join_id', how='left')
        df_merged['team'] = df_merged['sleeper_team'].fillna(df_merged['team'])
        df_merged = df_merged[df_merged['team'].notnull() & (df_merged['team'] != "FA")]
    else:
        df_merged['sleeper_status'] = None

    def format_status(row):
        sleeper_stat = str(row['sleeper_status']).upper() if pd.notnull(row.get('sleeper_status')) else ""
        rep_stat = str(row['report_status']).upper() if pd.notnull(row.get('report_status')) else ""

        if sleeper_stat == "NA":
            return "🛑 NA"
        if "DNR" in sleeper_stat or "DID NOT REPORT" in sleeper_stat:
            return "🚫 DNR"
        elif "PUP" in sleeper_stat:
            return "🏥 PUP"
        elif "SUS" in sleeper_stat:
            return "🛑 Suspendu"
        elif "IR" in sleeper_stat or "INJURED" in sleeper_stat:
            return "🏥 IR"
        elif "OUT" in sleeper_stat or "OUT" in rep_stat:
            return "🚨 Out"
        elif "DOUBTFUL" in sleeper_stat or "DOUBTFUL" in rep_stat:
            return "❌ Doubtful"
        elif "QUESTIONABLE" in sleeper_stat or "QUESTIONABLE" in rep_stat:
            return "⚠️ Questionable"
            
        return "🟢 Dispo"

    df_merged['Statut'] = df_merged.apply(format_status, axis=1)

    def get_advantage_indicator(rank):
        if pd.isnull(rank):
            return None
        elif rank >= 27:
            return "🔥 Gros avantage OFF"
        elif 20 <= rank <= 26:
            return "⚠️ Avantage OFF"
        elif 7 <= rank <= 12:
            return "🛡️ Avantage DEF"
        elif 1 <= rank <= 6:
            return "🔒 Gros avantage DEF"
        else:
            return None

    if def_rank in df_merged.columns:
        df_merged['Mismatch Alert'] = df_merged[def_rank].apply(get_advantage_indicator)
    else:
        df_merged['Mismatch Alert'] = None

    if m_avg in df_merged.columns:
        res_df = df_merged.dropna(subset=[m_avg, 'Mismatch Alert']).copy()
    else:
        res_df = pd.DataFrame()

    if not res_df.empty:
        if filter_advantage == "🔥 Gros avantages uniquement (OFF & DEF)":
            res_df = res_df[res_df['Mismatch Alert'].isin(["🔥 Gros avantage OFF", "🔒 Gros avantage DEF"])]

        for col in [m_avg, p_2026_avg, m_adj, m_l3, def_avg, def_2026_avg, def_rank, def_2026_rank, 'games_played_2025', 'games_played_2026']:
            if col in res_df.columns:
                res_df[col] = pd.to_numeric(res_df[col], errors='coerce').fillna(0).round(0).astype("Int64")

        col_player_avg = f'Moy. Brut ({base_year})'
        col_player_adj = f'Moy. Ajustée ({base_year})'
        name_col = 'player_name_x' if 'player_name_x' in res_df.columns else ('player_name' if 'player_name' in res_df.columns else 'Joueur')
        
        cols_display = [c for c in [
            name_col, 'position', 'Statut', 'team', 'opponent_team', 
            'games_played_2025', m_avg, m_adj, m_l3, 
            'games_played_2026', p_2026_avg, 
            def_avg, def_2026_avg, def_rank, def_2026_rank, 'Mismatch Alert'
        ] if c in res_df.columns]

        res_df = res_df[cols_display].rename(columns={
            name_col: 'Joueur',
            'position': 'Pos',
            'team': 'Équipe',
            'opponent_team': 'Adversaire',
            'games_played_2025': f'MJ {base_year}',
            m_avg: col_player_avg,
            m_adj: col_player_adj,
            m_l3: 'Derniers Matchs',
            'games_played_2026': 'MJ 2026',
            p_2026_avg: 'Moy. Brut 2026',
            def_avg: f'Yards Concédés/M aux {target_position} ({base_year})',
            def_2026_avg: 'Yards Concédés/M 2026',
            def_rank: f'Rang Déf. vs {target_position} ({base_year})',
            def_2026_rank: 'Rang Déf. 2026',
            'Mismatch Alert': 'Indicateur'
        })

        sort_col = col_player_adj if col_player_adj in res_df.columns else col_player_avg

        if sort_col in res_df.columns and 'Équipe' in res_df.columns:
            res_df = res_df.sort_values(by=sort_col, ascending=False)
            res_df['is_inactive'] = res_df['Statut'].ne("🟢 Dispo")
            res_df['available_count'] = (~res_df['is_inactive']).astype(int)
            res_df['cum_available'] = res_df.groupby('Équipe')['available_count'].cumsum()
            
            res_df = res_df[
                (~res_df['is_inactive'] & (res_df['cum_available'] <= max_players_per_team)) |
                (res_df['is_inactive'] & (res_df['cum_available'] < max_players_per_team))
            ]
            
            res_df = res_df.drop(columns=['is_inactive', 'available_count', 'cum_available'])
            res_df = res_df.sort_values(by=sort_col, ascending=False)
            res_df = res_df.reset_index(drop=True)
            res_df.index = res_df.index + 1

            title_suffix = f" — {selected_game}" if selected_game != "Toutes les rencontres" else ""
            st.subheader(f"Matchups Semaine {current_week}{title_suffix}")
            st.caption(f"🎯 **Critère sélectionné :** {selected_criterion} | Max. {max_players_per_team} {target_position} actif(s) par équipe")

            st.dataframe(res_df, width="stretch")
    else:
        st.warning("Aucune donnée ou aucun mismatch correspondant trouvé pour ce critère et ces filtres.")

# ==============================================================================
# TAB 2: MISMATCH SCORING ÉQUIPES
# ==============================================================================
with tab_teams:
    st.markdown("### ⚙️ Options de filtrage (Équipes)")

    week_team_schedule = schedule_2026[schedule_2026['week'] == current_week] if 'week' in schedule_2026.columns else schedule_2026

    if not week_team_schedule.empty and 'away_team' in week_team_schedule.columns and 'home_team' in week_team_schedule.columns:
        t_game_options = ["Toutes les rencontres"] + [
            f"{row['away_team']} @ {row['home_team']}" for _, row in week_team_schedule.iterrows()
        ]
    else:
        t_game_options = ["Toutes les rencontres"]
    selected_team_game = st.selectbox("Rencontre", options=t_game_options, key="game_teams")

    st.markdown("---")

    if not week_team_schedule.empty and 'home_team' in week_team_schedule.columns and 'away_team' in week_team_schedule.columns:
        home_matchups = week_team_schedule[['home_team', 'away_team']].copy().rename(columns={'home_team': 'team', 'away_team': 'opponent_team'})
        home_matchups['is_home'] = True

        away_matchups = week_team_schedule[['away_team', 'home_team']].copy().rename(columns={'away_team': 'team', 'home_team': 'opponent_team'})
        away_matchups['is_home'] = False

        team_matchups_2026 = pd.concat([home_matchups, away_matchups], ignore_index=True)
    else:
        team_matchups_2026 = pd.DataFrame(columns=['team', 'opponent_team', 'is_home'])

    if selected_team_game != "Toutes les rencontres" and " @ " in selected_team_game:
        away_t, home_t = selected_team_game.split(" @ ")
        team_matchups_2026 = team_matchups_2026[team_matchups_2026['team'].isin([away_t, home_t])]

    if not team_matchups_2026.empty:
        df_team_res = pd.merge(team_matchups_2026, team_scoring_2025, on='team', how='left')
        
        if not team_scoring_2026.empty:
            df_team_res = pd.merge(df_team_res, team_scoring_2026[['team', 'score_avg']], on='team', how='left', suffixes=('', '_2026'))
        else:
            df_team_res['score_avg_2026'] = None

        if not team_scoring_2025.empty:
            df_team_res = pd.merge(
                df_team_res, 
                team_scoring_2025[['team', 'allowed_avg', 'allowed_home', 'allowed_away']].rename(columns={'team': 'opponent_team'}), 
                on='opponent_team', 
                how='left',
                suffixes=('', '_opp')
            )
        else:
            df_team_res['allowed_avg'] = None
            df_team_res['allowed_home'] = None
            df_team_res['allowed_away'] = None

        if not team_scoring_2026.empty:
            df_team_res = pd.merge(
                df_team_res, 
                team_scoring_2026[['team', 'allowed_avg']].rename(columns={'team': 'opponent_team', 'allowed_avg': 'allowed_avg_2026'}), 
                on='opponent_team', 
                how='left'
            )
        else:
            df_team_res['allowed_avg_2026'] = None

        df_team_res['scoring_venue'] = df_team_res.apply(
            lambda r: r['score_home'] if r['is_home'] else r['score_away'], axis=1
        )
        df_team_res['opp_allowed_venue'] = df_team_res.apply(
            lambda r: r['allowed_away'] if r['is_home'] else r['allowed_home'], axis=1
        )

        cols_team_display = [
            'team', 'opponent_team', 'score_avg', 'score_avg_2026', 'score_home', 'score_away',
            'allowed_avg', 'allowed_avg_2026', 'allowed_away', 'allowed_home'
        ]

        for col in cols_team_display[2:]:
            if col in df_team_res.columns:
                df_team_res[col] = pd.to_numeric(df_team_res[col], errors='coerce').round(1)

        final_team_df = df_team_res[cols_team_display].rename(columns={
            'team': 'Équipe',
            'opponent_team': 'Équipe adverse',
            'score_avg': 'Moyenne points 2025',
            'score_avg_2026': 'Moyenne points 2026',
            'score_home': 'Scoring à domicile',
            'score_away': 'Scoring à l\'extérieur',
            'allowed_avg': 'Points concédés adv. 2025',
            'allowed_avg_2026': 'Points concédés adv. 2026',
            'allowed_away': 'Points concédés adv. à l\'extérieur',
            'allowed_home': 'Points concédés adv. à domicile'
        })

        final_team_df = final_team_df.reset_index(drop=True)
        final_team_df.index = final_team_df.index + 1

        t_title_suffix = f" — {selected_team_game}" if selected_team_game != "Toutes les rencontres" else ""
        st.subheader(f"Scoring Équipes Semaine {current_week}{t_title_suffix}")
        st.dataframe(final_team_df, width="stretch")
    else:
        st.warning("Aucune rencontre trouvée pour cette semaine.")

# ==============================================================================
# TAB 3: INFIRMERIE & PROFONDEUR
# ==============================================================================
with tab_injuries:
    st.markdown("### ⚙️ Options de filtrage (Infirmerie)")

    week_inj_schedule = schedule_2026[schedule_2026['week'] == current_week] if 'week' in schedule_2026.columns else schedule_2026
    
    if not week_inj_schedule.empty and 'home_team' in week_inj_schedule.columns and 'away_team' in week_inj_schedule.columns:
        teams_playing_this_week = set(week_inj_schedule['home_team'].dropna()).union(set(week_inj_schedule['away_team'].dropna()))
    else:
        teams_playing_this_week = set(roster_2026['team'].dropna().unique()) if 'team' in roster_2026.columns else set()

    available_teams_week = sorted(list(teams_playing_this_week))
    selected_inj_team = st.selectbox("Équipe", options=["Toutes les équipes de la semaine"] + available_teams_week, key="team_injuries")

    st.markdown("---")

    df_roster_full = roster_2026[roster_2026['team'].isin(teams_playing_this_week)].copy()

    # Jointure Depth Charts
    if not depth_charts.empty:
        if 'gsis_id' in depth_charts.columns and 'player_id' not in depth_charts.columns:
            depth_charts['player_id'] = depth_charts['gsis_id']
        
        # fallback sur pos_rank / depth_team
        depth_col = 'depth_team' if 'depth_team' in depth_charts.columns else ('pos_rank' if 'pos_rank' in depth_charts.columns else None)
        
        if depth_col and 'player_id' in depth_charts.columns:
            df_roster_full = pd.merge(
                df_roster_full, 
                depth_charts[['player_id', depth_col]].drop_duplicates(subset=['player_id']).rename(columns={depth_col: 'depth_team'}), 
                on='player_id', 
                how='left'
            )

    if 'depth_team' not in df_roster_full.columns:
        df_roster_full['depth_team'] = None

    # Jointure Rapport de blessure officiel (NFL)
    if not injuries_df.empty and 'week' in injuries_df.columns:
        inj_w = injuries_df[injuries_df['week'] == current_week]
        inj_k = 'player_id' if ('player_id' in df_roster_full.columns and 'player_id' in inj_w.columns) else 'player_name'
        cols_inj_w = [inj_k, 'report_status'] if 'report_status' in inj_w.columns else [inj_k]
        df_roster_full = pd.merge(df_roster_full, inj_w[cols_inj_w], on=inj_k, how='left')
    else:
        df_roster_full['report_status'] = None

    # Jointure Sleeper Status
    if not sleeper_df.empty:
        if 'player_id' in df_roster_full.columns and 'gsis_id' in sleeper_df.columns:
            df_roster_full = pd.merge(df_roster_full, sleeper_df[['gsis_id', 'sleeper_status']], left_on='player_id', right_on='gsis_id', how='left')
        elif 'player_name' in df_roster_full.columns and 'player_name' in sleeper_df.columns:
            df_roster_full = pd.merge(df_roster_full, sleeper_df[['player_name', 'sleeper_status']], on='player_name', how='left')
    else:
        df_roster_full['sleeper_status'] = None

    # Harmonisation et remplissage des trous
    def get_display_medical_status(row):
        rep = str(row['report_status']).strip() if pd.notnull(row.get('report_status')) and str(row.get('report_status')).lower() != 'none' else ""
        slp = str(row['sleeper_status']).strip() if pd.notnull(row.get('sleeper_status')) and str(row.get('sleeper_status')).lower() != 'none' else ""
        
        if rep:
            return rep.upper()
        if slp:
            return slp.upper()
        return "DISPO"

    df_roster_full['Statut Médical'] = df_roster_full.apply(get_display_medical_status, axis=1)

    slp_series = df_roster_full['sleeper_status'].astype(str).str.upper()
    rep_series = df_roster_full['report_status'].astype(str).str.upper()

    is_out = (
        slp_series.isin(["NA", "SUS"]) | 
        slp_series.str.contains("DNR|PUP|IR|OUT", na=False) | 
        rep_series.str.contains("OUT|PUP|IR", na=False)
    )
    is_doubtful = slp_series.str.contains("DOUBTFUL", na=False) | rep_series.str.contains("DOUBTFUL", na=False)
    is_quest = slp_series.str.contains("QUESTIONABLE", na=False) | rep_series.str.contains("QUESTIONABLE", na=False)

    df_roster_full['Status_Category'] = "AVAILABLE"
    df_roster_full.loc[is_quest, 'Status_Category'] = "QUESTIONABLE"
    df_roster_full.loc[is_doubtful, 'Status_Category'] = "DOUBTFUL"
    df_roster_full.loc[is_out, 'Status_Category'] = "OUT_IR_NA"

    if selected_inj_team != "Toutes les équipes de la semaine":
        df_roster_full = df_roster_full[df_roster_full['team'] == selected_inj_team].copy()

    available_players = df_roster_full[df_roster_full['Status_Category'] == "AVAILABLE"]

    def get_fast_replacement(row):
        team = row['team']
        pos = row['position']
        curr_depth = row['depth_team'] if pd.notnull(row['depth_team']) and str(row['depth_team']).isdigit() else 1

        cands = available_players[
            (available_players['team'] == team) & 
            (available_players['position'] == pos)
        ]

        if cands.empty:
            return "Aucun dispo"

        valid_depths = cands[cands['depth_team'] > curr_depth] if 'depth_team' in cands.columns else pd.DataFrame()
        if not valid_depths.empty:
            next_p = valid_depths.sort_values(by='depth_team').iloc[0]
        else:
            next_p = cands.iloc[0]

        d_str = f" (Depth {int(next_p['depth_team'])})" if pd.notnull(next_p.get('depth_team')) else ""
        return f"{next_p.get('player_name', next_p.get('full_name', 'Inconnu'))}{d_str}"

    injured_mask = df_roster_full['Status_Category'] != "AVAILABLE"
    df_roster_full['Remplaçant Proposé'] = "-"
    if injured_mask.any():
        df_roster_full.loc[injured_mask, 'Remplaçant Proposé'] = df_roster_full[injured_mask].apply(get_fast_replacement, axis=1)

    p_name_col = 'player_name' if 'player_name' in df_roster_full.columns else 'full_name'
    display_cols = [c for c in [p_name_col, 'position', 'team', 'depth_team', 'Statut Médical', 'Remplaçant Proposé'] if c in df_roster_full.columns]

    def render_injury_table(title, cat_code, default_msg):
        st.subheader(title)
        df_sub = df_roster_full[df_roster_full['Status_Category'] == cat_code]
        if not df_sub.empty:
            df_renamed = df_sub[display_cols].rename(columns={
                p_name_col: 'Nom du Joueur',
                'position': 'Poste',
                'team': 'Équipe',
                'depth_team': 'Ordre Chart'
            })
            st.dataframe(df_renamed.reset_index(drop=True), width="stretch")
        else:
            st.info(default_msg)

    render_injury_table("🛑 Absents Certains (OUT / IR / PUP / NA)", "OUT_IR_NA", "Aucun joueur confirmé absent pour cette sélection.")
    render_injury_table("❌ Incertains (DOUBTFUL)", "DOUBTFUL", "Aucun joueur doubtful pour cette sélection.")
    render_injury_table("⚠️ Sous réserve (QUESTIONABLE)", "QUESTIONABLE", "Aucun joueur questionable pour cette sélection.")
