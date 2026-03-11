from dataclasses import dataclass, field
from typing import List


@dataclass
class AgentMemory:
    short_term_events: List[str] = field(default_factory=list)

    def add(self, event: str) -> None:
        self.short_term_events.append(event)

    def tail(self, n: int = 12) -> List[str]:
        return self.short_term_events[-n:]
