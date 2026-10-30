"""The hollow-probe scan: which functions are probes, and which probe nothing."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from wiring_checks import scan_probes

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "pantry"


def probes_of(text: str, **kwargs) -> dict[str, dict]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "app").mkdir()
        (root / "app" / "web.py").write_text(textwrap.dedent(text), encoding="utf-8")
        return {row["probe"]: row for row in scan_probes(root, **kwargs)["probes"]}


class Kinds(unittest.TestCase):
    def test_constant_flag_only_and_calls(self) -> None:
        got = probes_of("""
            import db
            READY = False

            def healthz():
                return {"status": "ok"}

            def readyz():
                return jsonify(ok=True, checks=["db"])

            def livez(request):
                return JSONResponse({"ok": request.app.state.ready})

            def health():
                return {"db": db.ping()}

            async def readiness(pool):
                async with pool.acquire() as conn:
                    await conn.execute("select 1")
                return {"ok": True}

            def liveness():
                def later():
                    return db.ping()
                return {"ok": READY}

            def status():
                return {"ok": True}
        """)
        kinds = {name.rsplit(".", 1)[1]: row["kind"] for name, row in got.items()}
        self.assertEqual(kinds, {"healthz": "constant", "readyz": "constant", "livez": "flag_only", "health": "calls",
                                 "readiness": "calls", "liveness": "flag_only"})
        self.assertEqual(got["app.web.livez"]["reads"], ["request.app.state.ready"])
        self.assertEqual((got["app.web.health"]["calls"], got["app.web.health"]["reads"]), (["db.ping"], []))
        self.assertTrue(got["app.web.readiness"]["awaits"])
        self.assertEqual(got["app.web.liveness"]["calls"], [], "a nested function does not run when the probe runs")

    def test_routes_methods_and_lookalikes(self) -> None:
        got = probes_of("""
            app = object()

            @app.get("/healthz")
            def service():
                return {"up": True}

            @app.route("/api/ready?verbose=1")
            def api_ready():
                return check_all()

            @app.get("/healthy-food")
            def menu():
                return {"x": 1}

            class Probes:
                def ready(self):
                    return {"ok": self.ok}
        """)
        self.assertEqual(sorted(got), ["app.web.Probes.ready", "app.web.api_ready", "app.web.service"])
        self.assertEqual(got["app.web.service"]["why"], "route /healthz")
        self.assertEqual(got["app.web.api_ready"]["kind"], "calls")
        self.assertEqual(got["app.web.Probes.ready"]["kind"], "flag_only")

    def test_custom_probe_names(self) -> None:
        got = probes_of("def ping():\n    return 'pong'\n\ndef healthz():\n    return 'ok'\n", names=r"^ping$")
        self.assertEqual({name: row["kind"] for name, row in got.items()}, {"app.web.ping": "constant"})


class PantryApp(unittest.TestCase):
    def test_three_hollow_probes(self) -> None:
        result = scan_probes(FIXTURE / "src", base=FIXTURE)
        self.assertEqual(result["hollow"], ["pantry_app.health.healthz", "pantry_app.health.livez",
                                            "pantry_app.routes.service_check"])
        rows = {row["probe"]: row for row in result["probes"]}
        self.assertEqual((rows["pantry_app.health.readyz"]["kind"], rows["pantry_app.health.readyz"]["calls"]),
                         ("calls", ["store.ping"]))
        self.assertEqual(rows["pantry_app.routes.service_check"]["why"], "route /healthcheck")
        self.assertEqual(rows["pantry_app.health.livez"]["path"], "src/pantry_app/health.py")


if __name__ == "__main__":
    unittest.main()
