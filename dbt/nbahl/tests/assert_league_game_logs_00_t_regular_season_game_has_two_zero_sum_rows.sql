select
    season_sk,
    game_sk,
    count(*) as row_count,
    sum(plus_minus) as plus_minus_sum
from {{ ref("league_game_logs_00_t_regular_season") }}
group by season_sk, game_sk
having count(*) <> 2 or sum(plus_minus) <> 0
