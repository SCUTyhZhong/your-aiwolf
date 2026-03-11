from abc import ABC, abstractmethod
from typing import List, Optional
from app.api.schemas import Role, SkillName

class BaseRole(ABC):
    def __init__(self, slot_id: int, name: str):
        self.slot_id = slot_id
        self.name = name
        self.is_alive = True
        self.role_type: Role = Role.UNKNOWN
        self.is_human = False

    @abstractmethod
    def get_available_skills(self) -> List[SkillName]:
        pass

    def __repr__(self):
        return f"{self.role_type.value}(slot={self.slot_id}, alive={self.is_alive})"

class Werewolf(BaseRole):
    def __init__(self, slot_id: int, name: str):
        super().__init__(slot_id, name)
        self.role_type = Role.WEREWOLF

    def get_available_skills(self) -> List[SkillName]:
        return [SkillName.KILL, SkillName.VOTE]

class Seer(BaseRole):
    def __init__(self, slot_id: int, name: str):
        super().__init__(slot_id, name)
        self.role_type = Role.SEER

    def get_available_skills(self) -> List[SkillName]:
        return [SkillName.VERIFY, SkillName.VOTE]

class Witch(BaseRole):
    def __init__(self, slot_id: int, name: str):
        super().__init__(slot_id, name)
        self.role_type = Role.WITCH
        self.has_antidote = True
        self.has_poison = True

    def get_available_skills(self) -> List[SkillName]:
        skills = [SkillName.VOTE]
        if self.has_antidote:
            # MVP: reuse GUARD as antidote/save action.
            skills.append(SkillName.GUARD)
        if self.has_poison:
            skills.append(SkillName.POISON)
        return skills

class Villager(BaseRole):
    def __init__(self, slot_id: int, name: str):
        super().__init__(slot_id, name)
        self.role_type = Role.VILLAGER

    def get_available_skills(self) -> List[SkillName]:
        return [SkillName.VOTE]
