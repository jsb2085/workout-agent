from datetime import date

from app.cli import main
from app.graph.llm import GraphError, chat_model
from app.graph.models import LayoutDay, LoadedDay, LoadedLift, LoadedWeek, ProgressAssessment, WeekLayout
from app.graph.nodes import assemble_plan
from app.graph.planner import run_planner, run_week
from app.mcp.server import mcp
from app.schemas.weekly_plan import PlanningContext
from tests.test_mcp import _tool_payload


def _context() -> PlanningContext:
    return PlanningContext(
        week_start=date(2026, 9, 21),
        week_end=date(2026, 9, 27),
        recent_lifts=[
            {"lift": "bench press", "actual_weight": "195", "goal_weight": "185", "reps": 5},
            {"lift": "squat", "actual_weight": "225", "goal_weight": "235", "reps": 5},
        ],
        goals=[{"name": "Bench 225", "target": "225", "status": "Active"}],
        locations=[{"name": "Home gym", "equipment": "barbell, rack", "is_default": True}],
        default_location={"name": "Home gym", "equipment": "barbell, rack", "is_default": True},
        latest_body_stats={"date": "2026-09-18", "weight": "185", "bench": "195", "squat": "225"},
    )


def _progress() -> ProgressAssessment:
    return ProgressAssessment(
        summary="Bench is moving; squat is stalled.",
        priorities=["rebuild squat volume"],
        stalled_lifts=["squat"],
        progressing_lifts=["bench press"],
    )


def _layout() -> WeekLayout:
    return WeekLayout(
        focus="rebuild squat volume",
        notes="Home gym barbell work",
        days=[
            LayoutDay(date="2026-09-21", focus="upper", lifts=["bench press"]),
            LayoutDay(date="2026-09-22", rest=True, focus="rest"),
            LayoutDay(
                date="2026-09-23",
                focus="lower",
                lifts=["squat"],
                cardio_kind="walk",
                cardio_distance="2 miles",
            ),
        ],
    )


def _loaded() -> LoadedWeek:
    return LoadedWeek(
        days=[
            LoadedDay(
                date="2026-09-21",
                lifts=[LoadedLift(lift="bench press", reps=5, sets=3, goal_weight="200")],
            ),
            LoadedDay(
                date="2026-09-23",
                lifts=[LoadedLift(lift="squat", reps=5, sets=4, goal_weight="225")],
            ),
        ]
    )


async def _fake_complete(schema, system, user):
    if schema is ProgressAssessment:
        return _progress()
    if schema is WeekLayout:
        assert "Home gym" in user
        return _layout()
    if schema is LoadedWeek:
        assert "195" in user
        return _loaded()
    raise AssertionError(schema)


def test_assemble_plan_fills_week_and_skips_actual_weights():
    plan = assemble_plan(_context(), _progress(), _layout(), _loaded())
    assert len(plan.days) == 7
    assert plan.week_start == date(2026, 9, 21)
    assert plan.week_end == date(2026, 9, 27)
    assert plan.focus == "rebuild squat volume"
    assert plan.goals[0].name == "Bench 225"
    assert plan.locations[0].name == "Home gym"
    assert plan.body_stats.weight == "185"

    monday = plan.days[0]
    assert monday.lifts[0].lift == "bench press"
    assert monday.lifts[0].goal_weight == "200"
    assert monday.lifts[0].reps == 5
    assert monday.lifts[0].actual_weight is None

    tuesday = plan.days[1]
    assert tuesday.lifts == []
    assert tuesday.notes == "Rest"

    wednesday = plan.days[2]
    assert wednesday.lifts[0].lift == "squat"
    assert wednesday.lifts[0].goal_weight == "225"
    assert wednesday.cardio[0].kind == "walk"
    assert wednesday.cardio[0].distance == "2 miles"


async def test_run_planner_walks_the_four_nodes():
    plan = await run_planner(_context(), complete=_fake_complete)
    assert [day.date for day in plan.days] == [
        date(2026, 9, 21 + offset) for offset in range(7)
    ]
    assert plan.days[0].lifts[0].goal_weight == "200"
    assert all(lift.actual_weight is None for day in plan.days for lift in day.lifts)


async def test_run_week_pulls_then_pushes(monkeypatch):
    pulled = []
    pushed = []

    async def fake_pull(**kwargs):
        pulled.append(kwargs)
        return _context()

    async def fake_push(plan, **kwargs):
        pushed.append((plan, kwargs))
        return {"dry_run": kwargs["dry_run"], "title": plan.title, "lift_count": 2}

    monkeypatch.setattr("app.graph.planner.weekly_plan_service.pull_context", fake_pull)
    monkeypatch.setattr("app.graph.planner.weekly_plan_service.push_plan", fake_push)
    result = await run_week(
        week_start="2026-09-21",
        dry_run=True,
        include_videos=False,
        complete=_fake_complete,
    )
    assert pulled[0]["week_start"] == date(2026, 9, 21)
    assert result["push"]["dry_run"] is True
    assert result["plan"]["days"][0]["lifts"][0]["goal_weight"] == "200"
    assert pushed[0][1]["dry_run"] is True
    assert pushed[0][0].days[0].lifts[0].actual_weight is None


async def test_run_week_can_skip_push(monkeypatch):
    async def fake_pull(**kwargs):
        return _context()

    async def fail_push(*args, **kwargs):
        raise AssertionError("push should be skipped")

    monkeypatch.setattr("app.graph.planner.weekly_plan_service.pull_context", fake_pull)
    monkeypatch.setattr("app.graph.planner.weekly_plan_service.push_plan", fail_push)
    result = await run_week(week_start="2026-09-21", push=False, complete=_fake_complete)
    assert "push" not in result
    assert result["plan"]["title"].startswith("Week of Sep")


def test_cli_run_dry(monkeypatch, capsys):
    async def fake_run_week(**kwargs):
        assert kwargs["dry_run"] is True
        assert kwargs["include_videos"] is False
        assert kwargs["push"] is True
        assert kwargs["week_start"] == "2026-09-21"
        return {"plan": {"title": "Week of Sep 21–27"}, "push": {"dry_run": True}}

    monkeypatch.setattr("app.graph.planner.run_week", fake_run_week)
    assert main(["run", "--week-start", "2026-09-21", "--dry-run", "--no-videos"]) == 0
    printed = capsys.readouterr().out
    assert "Week of Sep 21" in printed
    assert '"dry_run": true' in printed


async def test_mcp_run_weekly_planner(monkeypatch):
    async def fake_run_week(**kwargs):
        assert kwargs["dry_run"] is True
        return {"plan": {"title": "Week of Sep 21–27", "focus": "squat"}, "push": {"dry_run": True}}

    monkeypatch.setattr("app.mcp.tools.run_week", fake_run_week)
    result = await mcp.call_tool(
        "run_weekly_planner",
        {"week_start": "2026-09-21", "dry_run": True, "include_videos": False},
    )
    payload = _tool_payload(result)
    assert payload["plan"]["focus"] == "squat"
    assert payload["push"]["dry_run"] is True


def test_chat_model_requires_api_key(monkeypatch):
    monkeypatch.setattr(
        "app.graph.llm.get_settings",
        lambda: type("S", (), {"openai_api_key": "", "openai_model": "gpt-5.6-luna", "openai_reasoning_effort": "medium"})(),
    )
    try:
        chat_model()
    except GraphError as exc:
        assert "OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("expected GraphError")


def test_chat_model_uses_luna(monkeypatch):
    monkeypatch.setattr(
        "app.graph.llm.get_settings",
        lambda: type(
            "S",
            (),
            {
                "openai_api_key": "sk-test",
                "openai_model": "gpt-5.6-luna",
                "openai_reasoning_effort": "medium",
            },
        )(),
    )
    model = chat_model()
    name = getattr(model, "model_name", None) or getattr(model, "model", None)
    assert name == "gpt-5.6-luna"
