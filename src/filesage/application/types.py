"""Tipos de resultado expuestos a presentation (sin acoplar a services internos).

La UI puede importar estos tipos para anotar variables y mostrar datos.
No debe instanciar SmartPlanner ni servicios: usar Engine / ApplicationAPI.
"""

from filesage.services.smart_planner import Confidence, PlanItem, SmartPlan
from filesage.services.smart_insights import Insight
from filesage.infrastructure.file_identity import FileIdentity

__all__ = ["Confidence", "PlanItem", "SmartPlan", "Insight", "FileIdentity"]
