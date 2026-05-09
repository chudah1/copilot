async def test_register_success(client):
    response = await client.post("/api/auth/register", json={"email": "new@example.com", "password": "secure123"})
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


async def test_register_duplicate_email(client, test_user):
    response = await client.post("/api/auth/register", json={"email": "test@example.com", "password": "secure123"})
    assert response.status_code == 409


async def test_login_success(client, test_user):
    response = await client.post("/api/auth/login", json={"email": "test@example.com", "password": "testpass123"})
    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_login_wrong_password(client, test_user):
    response = await client.post("/api/auth/login", json={"email": "test@example.com", "password": "wrong"})
    assert response.status_code == 401


async def test_refresh_token(client, test_user):
    login = await client.post("/api/auth/login", json={"email": "test@example.com", "password": "testpass123"})
    refresh_token = login.json()["refresh_token"]
    response = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert "access_token" in response.json()
