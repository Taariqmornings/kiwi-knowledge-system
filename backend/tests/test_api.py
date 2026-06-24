"""API endpoint integration tests."""


def test_root_endpoint(client):
    """Health check endpoint returns app metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "app" in data
    assert "version" in data
    assert data["status"] == "online"


def test_list_archives_empty(client):
    """Archives endpoint returns empty list when no archives exist."""
    response = client.get("/api/archives")
    assert response.status_code == 200
    assert response.json() == []


def test_list_archives_with_data(client, sample_archive):
    """Archives endpoint returns registered archives."""
    response = client.get("/api/archives")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "test-archive-001"
    assert data[0]["title"] == "Test Archive"


def test_list_categories(client, db_session):
    """Categories endpoint returns seeded categories."""
    response = client.get("/api/search/categories")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    # Should include seeded categories like "Medicine", "Science", etc.
    names = [c["name"] for c in data]
    assert "Medicine" in names
    assert "Science" in names


def test_search_no_results(client):
    """Search returns empty result with expected structure."""
    response = client.get("/api/search/query?q=nonexistent_term_xyz")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "total_count" in data
    assert "page" in data
    assert "total_pages" in data
    assert data["results"] == []


def test_search_requires_query(client):
    """Search without query returns 422."""
    response = client.get("/api/search/query")
    assert response.status_code == 422


def test_autocomplete_empty(client):
    """Autocomplete with non-matching query returns empty."""
    response = client.get("/api/search/autocomplete?q=zzznotexist")
    assert response.status_code == 200
    data = response.json()
    assert "suggestions" in data


def test_autocomplete_requires_query(client):
    """Autocomplete without query returns 422."""
    response = client.get("/api/search/autocomplete")
    assert response.status_code == 422


def test_delete_missing_archive(client):
    """Deleting non-existent archive returns 404."""
    response = client.delete("/api/archives/nonexistent-id")
    assert response.status_code == 404


def test_delete_existing_archive(client, sample_archive, db_session):
    """Deleting existing archive succeeds."""
    response = client.delete(f"/api/archives/{sample_archive.id}")
    assert response.status_code == 200
    # Verify it's gone
    response = client.get("/api/archives")
    assert len(response.json()) == 0


def test_cors_headers(client):
    """API returns CORS headers for allowed origins."""
    response = client.options(
        "/",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
