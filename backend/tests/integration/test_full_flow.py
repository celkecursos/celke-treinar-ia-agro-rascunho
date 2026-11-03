"""Fluxo completo com as APIs públicas e o modelo de verdade. Rode com a stack no ar:

docker compose --profile test run --rm backend-tests pytest -m integration -v
"""

import json
import os
import time

import httpx
import pytest

API = os.environ.get("INTEGRATION_API_URL", "http://backend:8000/api")
CODE = 5218805  # Rio Verde (GO)

pytestmark = pytest.mark.integration


def events(text):
    return [
        (dict(line.split(": ", 1) for line in block.splitlines())["event"], block)
        for block in text.strip().split("\n\n")
    ]


def test_register_collect_analyse_and_chat():
    with httpx.Client(base_url=API, timeout=900) as client:
        existing = client.get(f"/municipalities/{CODE}")
        created = existing.status_code == 404
        if created:
            assert client.post("/municipalities", json={"code": CODE}).status_code == 201
        for _ in range(180):
            municipality = client.get(f"/municipalities/{CODE}").json()
            if municipality["status"] != "coletando":
                break
            time.sleep(5)
        assert municipality["status"] == "pronto", municipality
        assert municipality["rain_days"] > 3000
        assert municipality["production_last_year"] >= 2023

        analysis = client.get(f"/analyses/{CODE}/soja").json()
        assert analysis["correlation"] is not None
        assert len(analysis["charts"]) == 7

        response = client.post(
            "/chat", json={"question": "Quanto choveu em Rio Verde (GO) entre 1 e 31 de janeiro de 2024?"}
        )
        names = [name for name, _ in events(response.text)]
        assert "tool_call" in names, response.text
        assert names[-1] == "done", response.text
        conversation_id = json.loads(events(response.text)[0][1].split("data: ", 1)[1])["id"]
        client.delete(f"/conversations/{conversation_id}")
        if created:
            assert client.delete(f"/municipalities/{CODE}").status_code == 204
