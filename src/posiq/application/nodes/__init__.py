"""Nodos del grafo: `async def nodo(state, deps) -> dict` con la actualización del estado."""

from posiq.application.nodes.analyze import analyze
from posiq.application.nodes.diferencial import diferencial
from posiq.application.nodes.intake import intake
from posiq.application.nodes.judge import judge
from posiq.application.nodes.market import market
from posiq.application.nodes.plan import plan
from posiq.application.nodes.prompts import prompts
from posiq.application.nodes.review import review_competidores, review_plan
from posiq.application.nodes.run import run
from posiq.application.nodes.write import write

__all__ = [
    "analyze",
    "diferencial",
    "intake",
    "judge",
    "market",
    "plan",
    "prompts",
    "review_competidores",
    "review_plan",
    "run",
    "write",
]
