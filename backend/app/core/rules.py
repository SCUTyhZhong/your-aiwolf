from typing import Dict, Iterable

from app.api.schemas import Role

# Standard 6-player MVP setup.
MVP_ROLE_DISTRIBUTION: Dict[Role, int] = {
	Role.WEREWOLF: 2,
	Role.SEER: 1,
	Role.WITCH: 1,
	Role.VILLAGER: 2,
}


def evaluate_winner(alive_roles: Iterable[Role]) -> str | None:
	"""Evaluate simplified MVP winner condition.

	Good side wins when no werewolf remains.
	Werewolves win when alive werewolves >= alive good players.
	"""
	alive = list(alive_roles)
	wolves = sum(1 for role in alive if role == Role.WEREWOLF)
	goods = len(alive) - wolves
	if wolves == 0:
		return "GOOD_GUYS_WIN"
	if wolves >= goods:
		return "WEREWOLVES_WIN"
	return None
