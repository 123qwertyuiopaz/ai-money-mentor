"""
Integration tests for auth and agent endpoints.
Agent tests that call NIM are automatically skipped without a real API key.
"""
import pytest
from tests.conftest import requires_nim


class TestAuth:
    def test_register(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "brand_new@example.com",
            "password": "password123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["email"] == "brand_new@example.com"

    def test_duplicate_register(self, client, registered_user):
        # Try to re-register the same unique email the fixture just created
        resp = client.post("/api/v1/auth/register", json={
            "email": registered_user["email"],
            "password": "password123",
        })
        assert resp.status_code == 409

    def test_login(self, client, registered_user):
        resp = client.post("/api/v1/auth/login", json={
            "email": registered_user["email"],
            "password": "testpass123",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, client, registered_user):
        resp = client.post("/api/v1/auth/login", json={
            "email": registered_user["email"],
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_get_me(self, client, auth_headers, registered_user):
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == registered_user["email"]

    def test_get_me_no_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_update_profile(self, client, auth_headers):
        resp = client.patch("/api/v1/auth/profile", json={
            "age": 30,
            "monthly_income": 100000,
            "monthly_expenses": 60000,
            "risk_profile": "moderate",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_invalid_risk_profile(self, client, auth_headers):
        resp = client.patch("/api/v1/auth/profile", json={
            "risk_profile": "yolo",
        }, headers=auth_headers)
        assert resp.status_code == 422

    def test_get_profile(self, client, auth_headers):
        client.patch("/api/v1/auth/profile", json={"monthly_income": 120000},
                     headers=auth_headers)
        resp = client.get("/api/v1/auth/profile", headers=auth_headers)
        assert resp.status_code == 200


class TestAgentEndpoints:
    def test_health_score_missing_token(self, client):
        resp = client.post("/api/v1/agents/health-score", json={})
        assert resp.status_code == 401

    def test_life_event_invalid_event(self, client, auth_headers):
        resp = client.post("/api/v1/agents/life-event", json={
            "event": "lottery_win",
        }, headers=auth_headers)
        assert resp.status_code == 422

    def test_agent_history_empty(self, client, auth_headers):
        resp = client.get("/api/v1/agents/history", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_portfolio_xray_no_data(self, client, auth_headers):
        """Should return 422 when no CAMS text and no saved portfolio."""
        resp = client.post("/api/v1/agents/portfolio-xray", json={},
                           headers=auth_headers)
        assert resp.status_code == 422

    def test_portfolio_upload_wrong_type(self, client, auth_headers):
        from io import BytesIO
        resp = client.post(
            "/api/v1/agents/portfolio-upload",
            files={"file": ("data.txt", BytesIO(b"some text"), "text/plain")},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @requires_nim
    def test_health_score_full(self, client, auth_headers):
        resp = client.post("/api/v1/agents/health-score", json={
            "monthly_income": 150000,
            "monthly_expenses": 80000,
            "emergency_fund": 480000,
            "life_cover": 15000000,
            "health_cover": 500000,
            "debt_emi": 20000,
            "monthly_investment": 30000,
            "has_term_plan": True,
            "age": 32,
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "total_score" in data["data"]
        assert "dimensions" in data["data"]

    @requires_nim
    def test_fire_planner(self, client, auth_headers):
        resp = client.post("/api/v1/agents/fire-planner", json={
            "age": 28,
            "monthly_income": 200000,
            "monthly_expenses": 100000,
            "target_retirement_age": 50,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @requires_nim
    def test_tax_wizard(self, client, auth_headers):
        resp = client.post("/api/v1/agents/tax-wizard", json={
            "annual_income": 1200000,
            "section_80c_used": 100000,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert "regime_comparison" in resp.json()["data"]

    @requires_nim
    def test_life_event_bonus(self, client, auth_headers):
        resp = client.post("/api/v1/agents/life-event", json={
            "event": "bonus",
            "event_amount": 500000,
            "monthly_income": 150000,
            "age": 35,
        }, headers=auth_headers)
        assert resp.status_code == 200


class TestHealth:
    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "docs" in resp.json()
