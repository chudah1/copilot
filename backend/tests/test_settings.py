async def test_get_settings_normalizes_unsupported_digest_frequency(client, auth_headers, db, test_user):
    test_user.preferences = {
        "digest_frequency": "daily",
        "notification_sensitivity": "all",
    }
    await db.commit()

    response = await client.get("/api/settings", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["digest_frequency"] == "weekly"


async def test_update_settings_persists_supported_values_only(client, auth_headers, db, test_user):
    response = await client.put(
        "/api/settings",
        json={"digest_frequency": "weekly", "notification_sensitivity": "thesis_breaking_only"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["digest_frequency"] == "weekly"
    assert response.json()["notification_sensitivity"] == "thesis_breaking_only"

    await db.refresh(test_user)
    assert test_user.preferences["digest_frequency"] == "weekly"
    assert test_user.preferences["notification_sensitivity"] == "thesis_breaking_only"
