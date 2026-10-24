from fastapi.testclient import TestClient
from depop.ui import app

client = TestClient(app)


def test_dashboard_html_serves():
    """Verify that the dashboard HTML serves with 200 OK."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Depop Demand Scraper" in response.text
    assert "<form id=\"scrapeForm\"" in response.text


def test_api_collections():
    """Verify that collections endpoint returns a JSON list."""
    response = client.get("/api/collections")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_api_products():
    """Verify that products endpoint returns saved products."""
    response = client.get("/api/products?limit=5")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
