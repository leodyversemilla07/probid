"""CLI command registration for probid."""

from app.commands.analysis import register_analysis_commands
from app.commands.awards import register_award_commands
from app.commands.profiles import register_profile_commands
from app.commands.search import register_search_commands

__all__ = [
    "register_analysis_commands",
    "register_award_commands",
    "register_profile_commands",
    "register_search_commands",
]
