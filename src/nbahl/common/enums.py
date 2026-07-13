from enum import StrEnum


class LeagueID(StrEnum):
    """NBA API league identifier codes."""

    NBA = "00"
    ABA = "01"
    G_LEAGUE = "20"
    WNBA = "10"


class PlayerOrTeamAbbreviation(StrEnum):
    """Indicates whether game log rows represent players or teams."""

    TEAM = "T"
    PLAYER = "P"


class SeasonTypeAllStar(StrEnum):
    """NBA season segment types accepted by the LeagueGameLog endpoint."""

    REGULAR_SEASON = "Regular Season"
    PRE_SEASON = "Pre Season"
    PLAYOFFS = "Playoffs"
    ALL_STAR = "All Star"


class Status(StrEnum):
    """Ingestion run outcome recorded in the pipeline metadata table."""

    SUCCESS = "Success"
    FAILURE = "Failure"


class Period(StrEnum):
    """NBA API period codes used by play-by-play endpoints."""

    ALL = "0"
