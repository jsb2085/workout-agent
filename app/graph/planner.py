from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.graph.llm import complete_structured
from app.graph.models import LoadedWeek, ProgressAssessment, WeekLayout
from app.graph.nodes import assemble_plan, assess_progress, assign_loads, plan_sessions
from app.schemas.weekly_plan import PlanningContext, WeeklyPlan
from app.services import weekly_plan as weekly_plan_service


class PlannerState(TypedDict, total=False):
    context: dict[str, Any]
    progress: dict[str, Any]
    layout: dict[str, Any]
    loaded: dict[str, Any]
    plan: dict[str, Any]


def build_planner(complete=complete_structured):
    async def progress_node(state: PlannerState) -> PlannerState:
        context = PlanningContext.model_validate(state["context"])
        result = await assess_progress(context, complete=complete)
        return {"progress": result.model_dump(mode="json")}

    async def layout_node(state: PlannerState) -> PlannerState:
        context = PlanningContext.model_validate(state["context"])
        progress = ProgressAssessment.model_validate(state["progress"])
        result = await plan_sessions(context, progress, complete=complete)
        return {"layout": result.model_dump(mode="json")}

    async def loads_node(state: PlannerState) -> PlannerState:
        context = PlanningContext.model_validate(state["context"])
        progress = ProgressAssessment.model_validate(state["progress"])
        layout = WeekLayout.model_validate(state["layout"])
        result = await assign_loads(context, progress, layout, complete=complete)
        return {"loaded": result.model_dump(mode="json")}

    async def assemble_node(state: PlannerState) -> PlannerState:
        context = PlanningContext.model_validate(state["context"])
        progress = ProgressAssessment.model_validate(state["progress"])
        layout = WeekLayout.model_validate(state["layout"])
        loaded = LoadedWeek.model_validate(state["loaded"])
        plan = assemble_plan(context, progress, layout, loaded)
        return {"plan": plan.model_dump(mode="json")}

    graph = StateGraph(PlannerState)
    graph.add_node("assess_progress", progress_node)
    graph.add_node("plan_sessions", layout_node)
    graph.add_node("assign_loads", loads_node)
    graph.add_node("assemble", assemble_node)
    graph.add_edge(START, "assess_progress")
    graph.add_edge("assess_progress", "plan_sessions")
    graph.add_edge("plan_sessions", "assign_loads")
    graph.add_edge("assign_loads", "assemble")
    graph.add_edge("assemble", END)
    return graph.compile()


async def run_planner(
    context: PlanningContext,
    *,
    complete=complete_structured,
) -> WeeklyPlan:
    graph = build_planner(complete=complete)
    result = await graph.ainvoke({"context": context.model_dump(mode="json")})
    return WeeklyPlan.model_validate(result["plan"])


async def run_week(
    *,
    week_start: str | None = None,
    week_end: str | None = None,
    dry_run: bool = False,
    include_videos: bool = True,
    push: bool = True,
    complete=complete_structured,
    store=None,
) -> dict[str, Any]:
    start = weekly_plan_service.parse_week_start(week_start)
    end = weekly_plan_service.week_end_for(start, week_end)
    context = await weekly_plan_service.pull_context(week_start=start, week_end=end, store=store)
    plan = await run_planner(context, complete=complete)
    payload: dict[str, Any] = {"plan": plan.model_dump(mode="json")}
    if push:
        payload["push"] = await weekly_plan_service.push_plan(
            plan,
            dry_run=dry_run,
            include_videos=include_videos,
            store=store,
        )
    return payload
