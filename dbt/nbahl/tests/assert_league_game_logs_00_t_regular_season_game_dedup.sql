with latest as (
    select
        trim(season_id) as season_id,
        trim(team_id) as team_id,
        trim(game_id) as game_id,
        max(_ingested_at) as _max_ingested_at
    from
        {{ source("bronze", "league_game_logs_00_t_regular_season") }}
    group by
        1, 2, 3
)

select t.*
from
    {{ ref("league_game_logs_00_t_regular_season") }} as t
inner join
    latest as l
    on
        t.season_id = l.season_id
        and t.team_id = l.team_id
        and t.game_id = l.game_id
where
    l._max_ingested_at <> t._ingested_at
