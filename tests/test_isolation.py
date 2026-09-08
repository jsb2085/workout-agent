from tests.conftest import auth_header

WORKOUT = {
    "lift": "squat",
    "goal_weight": "225",
    "reps": 5,
    "actual_weight": "205",
    "completed": False,
    "date_todo": "2026-09-05T10:00:00+00:00",
}


async def test_user_cannot_read_another_users_workout(client, alice_token, bob_token):
    created = await client.post(
        "/lifting-workouts/",
        headers=auth_header(alice_token),
        json=WORKOUT,
    )
    assert created.status_code == 201
    workout_id = created.json()["id"]

    bob_list = await client.get("/lifting-workouts/", headers=auth_header(bob_token))
    assert bob_list.status_code == 200
    assert bob_list.json() == []

    bob_get = await client.get(
        f"/lifting-workouts/{workout_id}",
        headers=auth_header(bob_token),
    )
    assert bob_get.status_code == 404

    alice_get = await client.get(
        f"/lifting-workouts/{workout_id}",
        headers=auth_header(alice_token),
    )
    assert alice_get.status_code == 200
    assert alice_get.json()["lift"] == "squat"


async def test_protein_crud_round_trip(client, alice_token):
    headers = auth_header(alice_token)
    created = await client.post(
        "/protein/",
        headers=headers,
        json={"grams_goal": 160, "grams_actual": 140, "date_todo": "2026-09-05T12:00:00+00:00"},
    )
    assert created.status_code == 201
    item_id = created.json()["id"]

    patched = await client.patch(
        f"/protein/{item_id}",
        headers=headers,
        json={"grams_actual": 160},
    )
    assert patched.status_code == 200
    assert patched.json()["grams_actual"] == 160

    deleted = await client.delete(f"/protein/{item_id}", headers=headers)
    assert deleted.status_code == 204

    missing = await client.get(f"/protein/{item_id}", headers=headers)
    assert missing.status_code == 404


async def test_cardio_and_steps_and_goals(client, alice_token):
    headers = auth_header(alice_token)

    cardio = await client.post(
        "/cardio/",
        headers=headers,
        json={
            "run": True,
            "distance": "3 miles",
            "reps": 1,
            "date_todo": "2026-09-06T08:00:00+00:00",
        },
    )
    assert cardio.status_code == 201

    steps = await client.post(
        "/steps/",
        headers=headers,
        json={"steps_goal": 10000, "steps_actual": 4200, "date_todo": "2026-09-06T08:00:00+00:00"},
    )
    assert steps.status_code == 201

    gym = await client.post(
        "/gym-locations/",
        headers=headers,
        json={"location_name": "Home gym", "description": "Garage rack"},
    )
    assert gym.status_code == 201

    goal = await client.post(
        "/performance-goals/",
        headers=headers,
        json={"goal_name": "Plate squat", "description": "Squat 135 for 5"},
    )
    assert goal.status_code == 201
    assert goal.json()["goal_name"] == "Plate squat"

    stats = await client.post(
        "/body-stats/",
        headers=headers,
        json={
            "height": "5'10\"",
            "weight": "180",
            "squat": "225",
            "bench": None,
            "deadlift": "315",
            "date": "2026-09-06T08:00:00+00:00",
        },
    )
    assert stats.status_code == 201
    assert stats.json()["squat"] == "225"
    assert stats.json()["bench"] is None
    assert stats.json()["overhead_press"] is None


async def test_user_cannot_read_another_users_body_stats(client, alice_token, bob_token):
    created = await client.post(
        "/body-stats/",
        headers=auth_header(alice_token),
        json={"height": "6'0\"", "weight": "200", "date": "2026-09-06T08:00:00+00:00"},
    )
    assert created.status_code == 201
    item_id = created.json()["id"]

    bob_list = await client.get("/body-stats/", headers=auth_header(bob_token))
    assert bob_list.json() == []

    bob_get = await client.get(f"/body-stats/{item_id}", headers=auth_header(bob_token))
    assert bob_get.status_code == 404


async def test_body_stats_can_set_a_lift_to_unknown(client, alice_token):
    headers = auth_header(alice_token)
    created = await client.post(
        "/body-stats/",
        headers=headers,
        json={
            "height": "5'8\"",
            "weight": "155",
            "squat": "185",
            "bench": "115",
            "date": "2026-09-06T08:00:00+00:00",
        },
    )
    assert created.status_code == 201
    item_id = created.json()["id"]

    patched = await client.patch(
        f"/body-stats/{item_id}",
        headers=headers,
        json={"bench": None},
    )
    assert patched.status_code == 200
    assert patched.json()["squat"] == "185"
    assert patched.json()["bench"] is None
