import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_EMBED_MODEL = "text-embedding-3-small"


async def embed_text_map(
    texts: list[str],
    *,
    model: str = DEFAULT_EMBED_MODEL,
) -> dict[str, list[float]]:
    unique = sorted({text.strip() for text in texts if text and text.strip()})
    if not unique or not settings.openai_api_key:
        return {}

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.embeddings.create(model=model, input=unique)
    except Exception as exc:  # pragma: no cover - network/SDK failure path
        logger.warning("Embedding request failed: %s", exc)
        return {}

    return {
        text: [float(value) for value in item.embedding]
        for text, item in zip(unique, response.data)
    }


async def embed_texts(
    texts: list[str],
    *,
    model: str = DEFAULT_EMBED_MODEL,
) -> list[list[float] | None]:
    by_text = await embed_text_map(texts, model=model)
    return [
        by_text.get(text.strip()) if text and text.strip() else None
        for text in texts
    ]


async def embed_text(
    text: str,
    *,
    model: str = DEFAULT_EMBED_MODEL,
) -> list[float] | None:
    values = await embed_texts([text], model=model)
    return values[0] if values else None
