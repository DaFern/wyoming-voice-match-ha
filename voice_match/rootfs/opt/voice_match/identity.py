"""Trust only the Ingress peer and fresh Core account/role data."""

import asyncio
import os

from aiohttp import ClientError, ClientSession, ClientTimeout

from voices import Denied


def actor_from_users(user_id, users):
    for user in users:
        if user.get("id") == user_id and user.get("is_active") and not user.get("system_generated"):
            return {"id": user_id, "name": user.get("name") or "Your voice",
                    "admin": bool(user.get("is_owner") or "system-admin" in user.get("group_ids", []))}
    raise Denied("Your Home Assistant account is unavailable")


async def users_from_core():
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise Denied("Home Assistant role verification is unavailable")
    try:
        async with ClientSession(timeout=ClientTimeout(total=8)) as session:
            async with session.ws_connect("ws://supervisor/core/websocket", max_msg_size=1024 * 1024) as ws:
                hello = await ws.receive_json(timeout=5)
                if hello.get("type") != "auth_required":
                    raise Denied("Home Assistant role verification failed")
                await ws.send_json({"type": "auth", "access_token": token})
                if (await ws.receive_json(timeout=5)).get("type") != "auth_ok":
                    raise Denied("Home Assistant role verification failed")
                await ws.send_json({"id": 1, "type": "config/auth/list"})
                result = await ws.receive_json(timeout=5)
                if not result.get("success") or not isinstance(result.get("result"), list):
                    raise Denied("Home Assistant role verification failed")
                return result["result"]
    except (ClientError, OSError, asyncio.TimeoutError, ValueError) as exc:
        raise Denied("Home Assistant role verification is unavailable") from exc


async def identify(request, lookup=users_from_core):
    # Never trust X-Forwarded-For or a browser-supplied admin flag.
    peer = request.transport.get_extra_info("peername") if request.transport else None
    if not peer or peer[0] != "172.30.32.2":
        raise Denied("Use Home Assistant Ingress to open Voice Match")
    user_id = request.headers.get("X-Remote-User-Id", "")
    if not user_id or len(user_id) > 128:
        raise Denied("Home Assistant did not provide a user identity")
    users = await lookup()
    return actor_from_users(user_id, users), users
