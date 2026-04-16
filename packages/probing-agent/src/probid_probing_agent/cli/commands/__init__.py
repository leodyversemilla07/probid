"""CLI command registrations."""

from probid_probing_agent.cli.commands.agent import register_agent_commands
from probid_probing_agent.cli.commands.analysis import register_analysis_commands
from probid_probing_agent.cli.commands.awards import register_award_commands
from probid_probing_agent.cli.commands.profiles import register_profile_commands
from probid_probing_agent.cli.commands.search import register_search_commands

__all__ = [
    "register_agent_commands",
    "register_analysis_commands",
    "register_award_commands",
    "register_profile_commands",
    "register_search_commands",
]
