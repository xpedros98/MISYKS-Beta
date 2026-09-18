"""sec.agenda: módulo de agenda de MISYKS (Google Calendar por OAuth, base
local cifrada). Anota reuniones, vistas y los plazos que calcula `procesal`;
no computa ninguna fecha.
"""
from .agent import SecAgenda

__all__ = ["SecAgenda"]
