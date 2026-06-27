"""Domain models — import from here to keep routes decoupled from file layout."""

from app.models.content import Material
from app.models.learning import Interaction, Scenario

__all__ = ["Material", "Scenario", "Interaction"]
