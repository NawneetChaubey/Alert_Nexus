"""
Backend API Tests for Global Recall & Compliance Alert Platform
Tests all endpoints: health, stats, recalls, alerts, watchlist, compliance, search, ingest, auth
"""
import os
import pytest
import requests
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_TOKEN = "test_session_harness"

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def auth_client(api_client):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {TEST_TOKEN}"})
    return api_client


class TestHealth:
    """Health endpoint tests"""
    
    def test_health_returns_ok(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print("✓ Health endpoint returns ok")


class TestStats:
    """Stats/ingestion endpoint tests"""
    
    def test_ingestion_stats_returns_data(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/stats/ingestion")
        assert response.status_code == 200
        data = response.json()
        
        # Verify >= 4500 normalized records
        assert data.get("total_normalized", 0) >= 4500, f"Expected >= 4500 records, got {data.get('total_normalized')}"
        
        # Verify severity distribution exists
        assert "severity" in data
        assert isinstance(data["severity"], dict)
        
        # Verify region distribution exists
        assert "region" in data
        assert isinstance(data["region"], dict)
        
        # Verify source distribution exists
        assert "source" in data
        assert isinstance(data["source"], dict)
        
        # Verify confidence buckets exist
        assert "confidence_buckets" in data
        assert isinstance(data["confidence_buckets"], dict)
        
        # Verify inferred field counts exist
        assert "inferred_field_counts" in data
        assert isinstance(data["inferred_field_counts"], dict)
        
        print(f"✓ Stats endpoint returns {data['total_normalized']} normalized records")
        print(f"  Severity: {data['severity']}")
        print(f"  Regions: {list(data['region'].keys())}")
        print(f"  Sources: {list(data['source'].keys())}")


class TestRecalls:
    """Recalls endpoint tests"""
    
    def test_recalls_no_filters_returns_paginated(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/recalls")
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        assert len(data["items"]) > 0
        
        # Verify recall structure
        recall = data["items"][0]
        assert "recall_id" in recall
        assert "product_name" in recall
        assert "severity" in recall
        assert "region" in recall
        assert "source" in recall
        
        print(f"✓ Recalls endpoint returns {len(data['items'])} items, total: {data['total']}")
    
    def test_recalls_filter_severity_high(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/recalls?severity=high")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) > 0
        for item in data["items"]:
            assert item["severity"] == "high"
        
        print(f"✓ Severity=high filter works, {len(data['items'])} items")
    
    def test_recalls_filter_region_eu(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/recalls?region=EU")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) > 0
        for item in data["items"]:
            assert item["region"] == "EU"
        
        print(f"✓ Region=EU filter works, {len(data['items'])} items")
    
    def test_recalls_filter_category_cosmetic(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/recalls?category=cosmetic")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) > 0
        for item in data["items"]:
            assert item["category"] == "cosmetic"
        
        print(f"✓ Category=cosmetic filter works, {len(data['items'])} items")
    
    def test_recalls_search_hydroquinone(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/recalls?q=hydroquinone")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) > 0
        # Verify search term appears in results
        found_match = False
        for item in data["items"]:
            text = f"{item.get('product_name', '')} {item.get('recall_reason', '')} {' '.join(item.get('ingredients', []))}".lower()
            if "hydroquinone" in text:
                found_match = True
                break
        assert found_match, "Search term 'hydroquinone' not found in results"
        
        print(f"✓ Search q=hydroquinone works, {len(data['items'])} items")
    
    def test_recall_detail_with_lineage(self, api_client):
        # First get a recall ID
        response = api_client.get(f"{BASE_URL}/api/recalls?limit=1")
        assert response.status_code == 200
        recall_id = response.json()["items"][0]["recall_id"]
        
        # Get detail
        response = api_client.get(f"{BASE_URL}/api/recalls/{recall_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert "recall" in data
        assert "lineage" in data
        assert data["recall"]["recall_id"] == recall_id
        assert isinstance(data["lineage"], list)
        
        print(f"✓ Recall detail returns recall + lineage for {recall_id}")
    
    def test_recall_explain_calls_llm(self, auth_client):
        """Test AI explanation endpoint - requires auth"""
        # Get a recall ID
        response = auth_client.get(f"{BASE_URL}/api/recalls?limit=1")
        assert response.status_code == 200
        recall_id = response.json()["items"][0]["recall_id"]
        
        # Call explain endpoint
        response = auth_client.post(f"{BASE_URL}/api/recalls/{recall_id}/explain")
        assert response.status_code == 200
        data = response.json()
        
        assert "explanation" in data
        assert "recall_id" in data
        assert len(data["explanation"]) > 50  # Should have meaningful content
        
        print(f"✓ Explain endpoint returns AI explanation for {recall_id}")
        print(f"  Explanation preview: {data['explanation'][:100]}...")
        
        # Test caching - second call should return cached
        response2 = auth_client.post(f"{BASE_URL}/api/recalls/{recall_id}/explain")
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["explanation"] == data["explanation"]
        print("✓ Second call returns cached explanation")


class TestCompliance:
    """Compliance/banned substances endpoint tests"""
    
    def test_compliance_returns_banned_substances(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/compliance")
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert "regions" in data
        assert len(data["items"]) > 0
        
        # Verify structure
        item = data["items"][0]
        assert "substance" in item
        assert "region" in item
        assert "reason" in item
        
        print(f"✓ Compliance endpoint returns {len(data['items'])} banned substances")
        print(f"  Regions: {data['regions']}")
    
    def test_compliance_filter_region_eu(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/compliance?region=EU")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) > 0
        for item in data["items"]:
            assert item["region"] == "EU"
        
        print(f"✓ Compliance region=EU filter works, {len(data['items'])} items")


class TestWatchlist:
    """Watchlist endpoint tests - requires auth"""
    
    def test_watchlist_get(self, auth_client):
        response = auth_client.get(f"{BASE_URL}/api/watchlist")
        assert response.status_code == 200
        data = response.json()
        
        assert "products" in data
        assert "ingredients" in data
        assert isinstance(data["products"], list)
        assert isinstance(data["ingredients"], list)
        
        print(f"✓ Watchlist GET returns products: {data['products']}, ingredients: {data['ingredients']}")
    
    def test_watchlist_add_product(self, auth_client):
        response = auth_client.post(f"{BASE_URL}/api/watchlist/products", json={"value": "TEST_Product_123"})
        assert response.status_code == 200
        data = response.json()
        
        assert "watchlist" in data
        assert "alerts_created" in data
        assert "TEST_Product_123" in data["watchlist"]["products"]
        
        print(f"✓ Add product works, alerts_created: {data['alerts_created']}")
    
    def test_watchlist_delete_product(self, auth_client):
        response = auth_client.delete(f"{BASE_URL}/api/watchlist/products/TEST_Product_123")
        assert response.status_code == 200
        data = response.json()
        
        assert "TEST_Product_123" not in data.get("products", [])
        print("✓ Delete product works")
    
    def test_watchlist_add_ingredient_triggers_backfill(self, auth_client):
        response = auth_client.post(f"{BASE_URL}/api/watchlist/ingredients", json={"value": "test_ingredient_xyz"})
        assert response.status_code == 200
        data = response.json()
        
        assert "watchlist" in data
        assert "alerts_created" in data
        assert "test_ingredient_xyz" in data["watchlist"]["ingredients"]
        
        print(f"✓ Add ingredient works, alerts_created: {data['alerts_created']}")
    
    def test_watchlist_delete_ingredient(self, auth_client):
        response = auth_client.delete(f"{BASE_URL}/api/watchlist/ingredients/test_ingredient_xyz")
        assert response.status_code == 200
        data = response.json()
        
        assert "test_ingredient_xyz" not in data.get("ingredients", [])
        print("✓ Delete ingredient works")
    
    def test_watchlist_suggestions(self, auth_client):
        response = auth_client.get(f"{BASE_URL}/api/watchlist/suggestions")
        assert response.status_code == 200
        data = response.json()
        
        assert "ingredients" in data
        assert isinstance(data["ingredients"], list)
        assert len(data["ingredients"]) > 0
        
        print(f"✓ Suggestions returns {len(data['ingredients'])} ingredients")


class TestAlerts:
    """Alerts endpoint tests - requires auth"""
    
    def test_alerts_returns_user_scoped(self, auth_client):
        response = auth_client.get(f"{BASE_URL}/api/alerts")
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert "unread" in data
        
        if len(data["items"]) > 0:
            alert = data["items"][0]
            assert "alert_id" in alert
            assert "severity" in alert
            assert "product" in alert
            assert "matched_on" in alert
            assert "confidence_score" in alert
        
        print(f"✓ Alerts returns {len(data['items'])} items, {data['unread']} unread")
    
    def test_alerts_filter_severity(self, auth_client):
        response = auth_client.get(f"{BASE_URL}/api/alerts?severity=high")
        assert response.status_code == 200
        data = response.json()
        
        for item in data["items"]:
            assert item["severity"] == "high"
        
        print(f"✓ Alerts severity filter works, {len(data['items'])} high severity alerts")
    
    def test_alerts_filter_matched_on(self, auth_client):
        response = auth_client.get(f"{BASE_URL}/api/alerts?matched_on=ingredient")
        assert response.status_code == 200
        data = response.json()
        
        for item in data["items"]:
            assert item["matched_on"] == "ingredient"
        
        print(f"✓ Alerts matched_on filter works, {len(data['items'])} ingredient matches")
    
    def test_alerts_mark_all_read(self, auth_client):
        response = auth_client.post(f"{BASE_URL}/api/alerts/read-all")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") == True
        print("✓ Mark all read works")

    def test_alerts_dismiss_and_restore(self, auth_client):
        # 1. Fetch active alerts
        res = auth_client.get(f"{BASE_URL}/api/alerts")
        assert res.status_code == 200
        active_items = res.json().get("items", [])
        if not active_items:
            pytest.skip("No active alerts present to test dismissal")

        target_id = active_items[0]["alert_id"]

        # 2. Dismiss the alert
        dismiss_res = auth_client.post(f"{BASE_URL}/api/alerts/{target_id}/dismiss")
        assert dismiss_res.status_code == 200
        assert dismiss_res.json().get("ok") == True
        assert dismiss_res.json().get("dismissed") == True

        # 3. Verify it is excluded from active alerts
        after_dismiss = auth_client.get(f"{BASE_URL}/api/alerts")
        assert after_dismiss.status_code == 200
        after_ids = [a["alert_id"] for a in after_dismiss.json().get("items", [])]
        assert target_id not in after_ids, "Dismissed alert should not appear in active alerts"

        # 4. Verify it is present in dismissed view
        dismissed_view = auth_client.get(f"{BASE_URL}/api/alerts?status=dismissed")
        assert dismissed_view.status_code == 200
        dismissed_ids = [a["alert_id"] for a in dismissed_view.json().get("items", [])]
        assert target_id in dismissed_ids, "Dismissed alert should appear in status=dismissed query"

        # 5. Restore the alert
        restore_res = auth_client.post(f"{BASE_URL}/api/alerts/{target_id}/restore")
        assert restore_res.status_code == 200
        assert restore_res.json().get("ok") == True
        assert restore_res.json().get("dismissed") == False

        # 6. Verify it is back in active alerts
        restored_view = auth_client.get(f"{BASE_URL}/api/alerts")
        assert restored_view.status_code == 200
        restored_ids = [a["alert_id"] for a in restored_view.json().get("items", [])]
        assert target_id in restored_ids, "Restored alert should reappear in active alerts"
        print(f"✓ Alert {target_id} dismiss and restore cycle verified")

    def test_alerts_dismiss_invalid_id(self, auth_client):
        response = auth_client.post(f"{BASE_URL}/api/alerts/invalid_id_not_found/dismiss")
        assert response.status_code == 404
        print("✓ Dismiss non-existent alert returns 404")


class TestSearch:
    """Global search endpoint tests"""
    
    def test_search_returns_recalls_ingredients_banned(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/search?q=hydro")
        assert response.status_code == 200
        data = response.json()
        
        assert "recalls" in data
        assert "ingredients" in data
        assert "banned" in data
        
        # Should find hydroquinone-related results
        total_results = len(data["recalls"]) + len(data["ingredients"]) + len(data["banned"])
        assert total_results > 0
        
        print(f"✓ Search returns recalls: {len(data['recalls'])}, ingredients: {len(data['ingredients'])}, banned: {len(data['banned'])}")


class TestAuth:
    """Auth endpoint tests"""
    
    def test_auth_me_with_bearer_token(self, auth_client):
        response = auth_client.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        
        assert "user_id" in data
        assert data["user_id"] == "test-user-harness"
        
        print(f"✓ Auth /me returns user: {data['user_id']}")
    
    def test_auth_me_without_token_returns_401(self, api_client):
        # Create a new session without auth
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401
        
        print("✓ Auth /me without token returns 401")
    
    def test_auth_logout(self, auth_client):
        response = auth_client.post(f"{BASE_URL}/api/auth/logout")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") == True
        print("✓ Auth logout works")


class TestIngest:
    """Ingest/upload endpoint tests - requires auth"""
    
    def test_ingest_upload_csv(self, auth_client):
        # Create a minimal test CSV
        csv_content = """product_name,recall_reason,severity
TEST_Product_Upload,Test recall reason for upload,high"""
        
        files = {
            'file': ('test_upload.csv', csv_content, 'text/csv')
        }
        
        # Remove Content-Type header for multipart
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        
        response = requests.post(
            f"{BASE_URL}/api/ingest/upload",
            files=files,
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "source_file" in data
        assert "normalized" in data
        
        print(f"✓ Ingest upload works, normalized: {data.get('normalized', 0)} records")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
