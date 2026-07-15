"""Smoke-test the configured chat and vision providers.

Sends one text completion and one image completion through the same settings and
LiteLLM path the app uses. The point is to confirm a provider/endpoint actually
accepts image inputs before you rely on it -- some coding-plan proxies (e.g. the
Z.AI GLM Coding Plan) silently strip or reject image parts even when the
underlying model is multimodal.

Usage:
    uv run python scripts/check_vision.py
    uv run python scripts/check_vision.py --image path/to/photo.jpg

Configuration is read from the environment / .env exactly like the app
(app.config.Settings): LLM_MODEL, VISION_MODEL, LLM_API_BASE, LLM_API_KEY,
VISION_API_BASE, VISION_API_KEY, OPENAI_API_KEY.
"""

import argparse
import asyncio
import base64
import mimetypes
import struct
import zlib

from app.config import get_settings
from app.services.llm import LLMService


def _make_test_png(width: int = 96, height: int = 96) -> bytes:
    """Build a valid solid-red PNG using only the standard library."""

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        body = chunk_type + data
        crc = zlib.crc32(body) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + body + struct.pack(">I", crc)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit truecolor
    row = bytes((220, 40, 40)) * width
    raw = bytearray()
    for _ in range(height):
        raw.append(0)  # per-scanline filter type: none
        raw.extend(row)
    idat = zlib.compress(bytes(raw), 9)
    return signature + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def _data_url(image_bytes: bytes, mime: str = "image/png") -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _load_image_data_url(path: str) -> str:
    with open(path, "rb") as handle:
        image_bytes = handle.read()
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    return _data_url(image_bytes, mime)


def _describe(kwargs: dict[str, str]) -> str:
    base = kwargs.get("api_base", "(provider default)")
    has_key = "yes" if kwargs.get("api_key") else "no (env fallback)"
    return f"api_base={base}  api_key_set={has_key}"


async def _run(image_path: str | None) -> int:
    settings = get_settings()
    service = LLMService(settings)

    print(f"chat   : {settings.llm_model}    {_describe(settings.chat_call_kwargs())}")
    print(f"vision : {settings.vision_model}    {_describe(settings.vision_call_kwargs())}")
    print("-" * 70)

    ok = True

    try:
        reply = await service.chat(
            [{"role": "user", "content": "Reply with exactly: OK"}], temperature=0
        )
        print(f"[chat]   PASS -> {reply.strip()[:120]}")
    except Exception as exc:
        ok = False
        print(f"[chat]   FAIL -> {type(exc).__name__}: {str(exc)[:300]}")

    if image_path:
        image_data_url = _load_image_data_url(image_path)
        prompt = "Describe this image in one short sentence."
    else:
        image_data_url = _data_url(_make_test_png())
        prompt = "What is the dominant color of this image? Answer with one word."

    try:
        reply = await service.vision(
            text=prompt, image_data_urls=[image_data_url], temperature=0
        )
        print(f"[vision] PASS -> {reply.strip()[:200]}")
    except Exception as exc:
        ok = False
        print(f"[vision] FAIL -> {type(exc).__name__}: {str(exc)[:300]}")
        print("         A failure here usually means the endpoint rejects image inputs.")

    print("-" * 70)
    print("RESULT:", "all checks passed" if ok else "one or more checks FAILED")
    return 0 if ok else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test chat + vision providers.")
    parser.add_argument("--image", help="Path to a real image instead of the generated one.")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.image)))


if __name__ == "__main__":
    main()
