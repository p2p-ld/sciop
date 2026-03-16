def test_api_docs_render(client):
    """The API docs should load and not fail to load!!!"""
    response = client.get("/docs/api")
    assert response.status_code == 200
