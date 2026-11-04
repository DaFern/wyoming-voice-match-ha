"""Check Wyoming discovery, not just an open socket; does not run inference."""

import asyncio

from wyoming.client import AsyncClient
from wyoming.info import Describe, Info


async def check(uri="tcp://127.0.0.1:10350"):
    async with AsyncClient.from_uri(uri) as client:
        await client.write_event(Describe().event())
        event = await client.read_event()
        if event is None or not Info.is_type(event.type) or not Info.from_event(event).asr:
            raise RuntimeError("Wyoming ASR discovery unavailable")


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(check(), timeout=10))
