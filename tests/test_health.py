"""Health endpoint tests."""


def test_health_live(client) -> None:
    response = client.get('/health/live')
    assert response.status_code == 200
    assert response.json()['status'] == 'alive'


def test_health_ready(client) -> None:
    response = client.get('/health/ready')
    # May be 200 (ready) or 503 (degraded) depending on ChromaDB state
    assert response.status_code in (200, 503)
    data = response.json()
    assert 'status' in data
    assert data['status'] in ('ready', 'degraded')


def test_health_ready_returns_checks(client) -> None:
    response = client.get('/health/ready')
    data = response.json()
    assert 'checks' in data
    assert 'generation_backend' in data
