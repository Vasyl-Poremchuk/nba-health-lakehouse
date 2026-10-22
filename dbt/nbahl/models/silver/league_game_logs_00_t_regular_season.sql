with
cleaned as (
    select
        cast(game_date as date) as game_date,
        cast(`min` as smallint) as `min`,
        cast(fgm as smallint) as fgm,
        cast(fga as smallint) as fga,
        cast(fg_pct as decimal(4, 3)) as fg_pct,
        cast(fg3m as smallint) as fg3m,
        cast(fg3a as smallint) as fg3a,
        cast(fg3_pct as decimal(4, 3)) as fg3_pct,
        cast(ftm as smallint) as ftm,
        cast(fta as smallint) as fta,
        cast(ft_pct as decimal(4, 3)) as ft_pct,
        cast(oreb as smallint) as oreb,
        cast(dreb as smallint) as dreb,
        cast(reb as smallint) as reb,
        cast(ast as smallint) as ast,
        cast(stl as smallint) as stl,
        cast(blk as smallint) as blk,
        cast(tov as smallint) as tov,
        cast(pf as smallint) as pf,
        cast(pts as smallint) as pts,
        cast(plus_minus as smallint) as plus_minus,
        _bronze_path,
        _source_name,
        _ingested_at,
        trim(season_id) as season_id,
        trim(team_id) as team_id,
        trim(team_abbreviation) as team_abbreviation,
        trim(team_name) as team_name,
        trim(game_id) as game_id,
        trim(matchup) as matchup,
        trim(wl) as wl,
        trim(season) as season
    from {{ source("bronze", "league_game_logs_00_t_regular_season") }}
),

keyed as (
    select
        *,
        sha2(season_id, 256) as season_sk,
        sha2(team_id, 256) as team_sk,
        sha2(game_id, 256) as game_sk
    from cleaned
),

ranked as (
    select
        *,
        row_number() over (
            partition by season_sk, team_sk, game_sk
            order by _ingested_at desc, _bronze_path desc
        ) as rn
    from keyed
)

select
    season_sk,
    season_id,
    season,
    team_sk,
    team_id,
    team_abbreviation,
    team_name,
    game_sk,
    game_id,
    game_date,
    matchup,
    wl,
    `min`,
    fgm,
    fga,
    fg_pct,
    fg3m,
    fg3a,
    fg3_pct,
    ftm,
    fta,
    ft_pct,
    oreb,
    dreb,
    reb,
    ast,
    stl,
    blk,
    tov,
    pf,
    pts,
    plus_minus,
    _bronze_path,
    _source_name,
    _ingested_at,
    current_timestamp() as _processed_at
from ranked
where rn = 1
