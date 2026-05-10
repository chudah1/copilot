async def test_list_digests_empty(client, auth_headers):
    response = await client.get("/api/digests", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_list_digests_requires_auth(client):
    response = await client.get("/api/digests")
    assert response.status_code == 403
