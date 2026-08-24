import re

import pytest


def test_cors_allows_penkeep_vercel_preview_but_not_arbitrary_vercel_app():
    from app.main import _cors_origin_regex

    pattern = _cors_origin_regex()

    assert re.fullmatch(
        pattern,
        "https://penkeep-o70wvzq0c-ychudah-5081s-projects.vercel.app",
    )
    assert re.fullmatch(pattern, "https://penkeep-git-main-ychudah-5081s-projects.vercel.app")
    assert not re.fullmatch(pattern, "https://other-app-ychudah-5081s-projects.vercel.app")
    assert not re.fullmatch(pattern, "https://attacker.vercel.app")


@pytest.mark.asyncio
async def test_cors_middleware_returns_preview_allow_origin_header(client):
    origin = "https://penkeep-o70wvzq0c-ychudah-5081s-projects.vercel.app"

    response = await client.get("/health", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
