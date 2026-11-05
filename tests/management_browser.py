"""Optional real-Chromium UI checks against loopback-only synthetic state.

Run with the isolated aiohttp test Python and --output pointing to an approved
cache directory. This never connects to Home Assistant or uses HA credentials.
"""

import argparse
import asyncio
import base64
import json
import shutil
import tempfile
from pathlib import Path

from aiohttp import ClientSession, web

STATIC = Path(__file__).resolve().parents[1] / "voice_match/rootfs/opt/voice_match/static"


async def review(output):
    output.mkdir(parents=True, exist_ok=True)
    own = {"id": "alice-profile", "owner": "alice", "name": "Alice", "enrolled": True,
           "recording_bytes": 0, "personal_instructions": ""}
    foreign = dict(own, id="bob-profile", owner="bob", name="Bob")
    state = {"user": {"id": "alice", "name": "Alice", "admin": False},
             "csrf": "synthetic-csrf", "profiles": [], "learning": False,
             "job": None, "engine": "ready", "learning_setup": {"paired": True}}
    calls = []

    async def page(request):
        return web.FileResponse(STATIC / "index.html")

    async def get_state(request):
        return web.json_response(state)

    async def action(request):
        data = await request.json()
        calls.append(data)
        assert request.headers["X-Voice-CSRF"] == "synthetic-csrf"
        assert data == {"action": "create_own_profile", "name": "Alice", "confirm": True}
        state["profiles"] = [dict(own, enrolled=False)]
        return web.json_response({"ok": True, "id": own["id"]})

    app = web.Application()
    app.router.add_get("/", page)
    app.router.add_get("/api/state", get_state)
    app.router.add_post("/api/action", action)
    app.router.add_static("/static/", STATIC)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix="voice-match-browser-") as profile:
            process = await asyncio.create_subprocess_exec(
                shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
                "--no-first-run", "--disable-background-networking", "--disable-sync",
                "--remote-debugging-port=0", f"--user-data-dir={profile}", "about:blank",
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
            )
            try:
                async with asyncio.timeout(20):
                    while True:
                        line = await process.stderr.readline()
                        if not line:
                            raise RuntimeError("Chromium exited before debugging was available")
                        if b"DevTools listening on " in line:
                            endpoint = line.decode().split("DevTools listening on ", 1)[1].strip()
                            break
                async with ClientSession() as client, client.ws_connect(endpoint, max_msg_size=8 * 1024 * 1024) as ws:
                    serial = 0

                    async def call(method, params=None, session=None):
                        nonlocal serial
                        serial += 1
                        request_id = serial
                        payload = {"id": request_id, "method": method, "params": params or {}}
                        if session:
                            payload["sessionId"] = session
                        await ws.send_json(payload)
                        async with asyncio.timeout(20):
                            while True:
                                message = await ws.receive_json()
                                if message.get("id") == request_id:
                                    assert "error" not in message, message
                                    return message.get("result", {})

                    target = await call("Target.createTarget", {"url": "about:blank"})
                    attached = await call("Target.attachToTarget", {"targetId": target["targetId"], "flatten": True})
                    session = attached["sessionId"]

                    async def evaluate(expression):
                        value = await call("Runtime.evaluate", {"expression": expression,
                            "awaitPromise": True, "returnByValue": True}, session)
                        assert "exceptionDetails" not in value, value
                        return value["result"].get("value")

                    async def wait_for(expression):
                        async with asyncio.timeout(15):
                            while not await evaluate(expression):
                                await asyncio.sleep(0.05)

                    async def click(text):
                        result = await evaluate("(() => { const button = [...document.querySelectorAll('button')]"
                            f".find(b => b.textContent === {json.dumps(text)} && b.getClientRects().length);"
                            "if (!button || button.disabled) return false; button.click(); return true; })()")
                        assert result, text

                    async def screenshot(name):
                        await evaluate("document.fonts.ready")
                        assert await evaluate("document.documentElement.scrollWidth <= innerWidth"), name
                        image = await call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False}, session)
                        (output / name).write_bytes(base64.b64decode(image["data"]))

                    await call("Emulation.setDeviceMetricsOverride", {
                        "width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True,
                    }, session)
                    await call("Page.navigate", {"url": f"http://127.0.0.1:{port}/"}, session)
                    await wait_for("typeof state !== 'undefined' && state?.user.id === 'alice'")
                    assert await evaluate("$('administration').hidden && $('wizard').hidden")
                    await screenshot("01-add-my-voice-mobile.png")
                    await click("Add my voice")
                    assert await evaluate("document.activeElement.id === 'wizard-title'")
                    await evaluate("$('name').value = 'Alice'")
                    await click("Create my voice profile")
                    await wait_for("!busy && !$('learning-help').hidden")
                    assert len(calls) == 1
                    assert await evaluate("document.activeElement.id === 'learning-help-title'")
                    await screenshot("02-learning-steps-mobile.png")
                    state["profiles"] = [own]
                    await evaluate("refresh(false)")
                    await evaluate("$('close-learning-help').click(); scrollTo(0, 0)")
                    await screenshot("03-voice-ready-mobile.png")
                    assert await evaluate("$('own-profile').textContent.includes('Saved recordings: none')")
                    assert await evaluate("!$('own-profile').textContent.includes('0.0 MB')")
                    state["profiles"] = [dict(own, pending="synthetic-pending", recording_bytes=32000)]
                    await evaluate("refresh(false)")
                    await click("Resume learning")
                    assert await evaluate("$('learning-entry-step').textContent.includes('separate')")
                    await screenshot("04-resume-mobile.png")
                    state["learning_setup"] = {"paired": False}
                    await evaluate("refresh(false)")
                    assert await evaluate("$('learning-help-status').textContent.includes(\"isn't set up yet\")")
                    state.update(user={"id": "alice", "name": "Alice", "admin": True},
                                 profiles=[own, foreign], accounts=[{"id": "alice", "name": "Alice"}, {"id": "bob", "name": "Bob"}])
                    await evaluate("refresh(false)")
                    assert not await evaluate("$('administration').hidden")
                    await evaluate("$('administration').open = true; $('administration').scrollIntoView()")
                    assert not await evaluate("[...$('profiles').querySelectorAll('button')].some(b => /Learn my voice|Resume learning/.test(b.textContent))")
                    await screenshot("05-admin-mobile.png")
                    await call("Emulation.setDeviceMetricsOverride", {
                        "width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False,
                    }, session)
                    await evaluate("$('administration').open = false; $('learning-help').hidden = true; scrollTo(0, 0)")
                    await screenshot("06-desktop.png")
                    state.update(user={"id": "bob", "name": "Bob", "admin": False}, profiles=[foreign])
                    await evaluate("refresh(false)")
                    assert await evaluate("$('administration').hidden && $('learning-help').hidden")
                    assert await evaluate("!$('own-profile').textContent.includes('Alice')")
                    assert len(calls) == 1, "No recording, handoff or deletion calls"
                    # Let Chromium flush/stop its children before removing its
                    # temporary profile; terminating only the parent can race
                    # outstanding child writes during TemporaryDirectory cleanup.
                    await call("Browser.close")
                    async with asyncio.timeout(15):
                        await process.wait()
            finally:
                if process.returncode is None:
                    process.terminate()
                    await process.wait()
                process = None
        print("Chromium mobile/desktop checks passed; synthetic previews:", output)
    finally:
        if process is not None and process.returncode is None:
            process.terminate()
            await process.wait()
        await runner.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if not shutil.which("chromium"):
        parser.error("Chromium is required for the optional browser review")
    asyncio.run(review(arguments.output))
