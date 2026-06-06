"""Locust load test for the LLM Ops RAG API.

Run:

    locust -f benchmarks/locustfile.py \
           --host http://localhost:8000 \
           --users 50 --spawn-rate 10 \
           --run-time 6m \
           --headless --csv benchmarks/results/run-c50

The 80/20 split in `TaskSet.tasks` simulates a dashboard workload: mostly
queries, with a sprinkling of corpus-status probes. The question pool is
drawn from the 18-question golden QA set so repetition characteristics
roughly match real usage.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

from locust import HttpUser, between, task

API_KEY = os.environ.get('LLM_OPS_API_KEY', 'dev-admin-key')
GOLDEN_QA_PATH = Path(__file__).resolve().parent.parent / 'data' / 'golden_qa' / 'golden_qa_v1.json'


def _load_questions() -> list[str]:
    try:
        data = json.loads(GOLDEN_QA_PATH.read_text())
        return [item['question'] for item in data if 'question' in item]
    except (FileNotFoundError, json.JSONDecodeError):
        # Fallback set so the load test still runs if the golden QA file moves
        return [
            'What are the first steps in incident response?',
            'What is the notification timeline for a P1 incident?',
            'How should digital evidence be acquired?',
            'What are the data classification tiers?',
            'Is MFA required for system access?',
        ]


QUESTIONS = _load_questions()


class RagUser(HttpUser):
    """Simulated RAG-API user."""

    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.headers = {
            'X-API-Key': API_KEY,
            'Content-Type': 'application/json',
        }

    @task(8)
    def query(self) -> None:
        question = random.choice(QUESTIONS)
        payload = {
            'question': question,
            'top_k': 5,
            'enable_citations': True,
        }
        self.client.post(
            '/v1/query',
            headers=self.headers,
            json=payload,
            name='/v1/query',
        )

    @task(1)
    def corpus_status(self) -> None:
        self.client.get(
            '/v1/admin/corpus/status',
            headers=self.headers,
            name='/v1/admin/corpus/status',
        )

    @task(1)
    def readiness(self) -> None:
        # No auth required on health endpoints
        self.client.get('/health/ready', name='/health/ready')
