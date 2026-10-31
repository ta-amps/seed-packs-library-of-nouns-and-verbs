"""Baseten <= 2,000,000 TPM async token-bucket burst swarm client with fenced lease safety."""

from __future__ import annotations

import asyncio
import hashlib
import http.server
import json
import os
import threading
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class FencedWorkerClaim:
    """Tessera worker lease claim metadata required before spending partner tokens."""

    task_id: str
    fencing_token: int
    remaining_lease_seconds: float
    prompt: str
    estimated_prompt_tokens: int
    max_completion_tokens: int
    model: str = "meta-llama/Llama-3.3-70B-Instruct"


class VirtualClock:
    """Deterministic or wall-clock monotonic timer for exact 2M TPM window verification."""

    def __init__(self, virtual: bool = False) -> None:
        self.virtual = virtual
        self._now = 0.0

    def now(self) -> float:
        if self.virtual:
            return self._now
        return asyncio.get_running_loop().time()

    async def sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        if self.virtual:
            self._now += seconds
            await asyncio.sleep(0)
        else:
            await asyncio.sleep(seconds)


class AsyncTokenBucket2M:
    """Sliding 60-second window token limiter strictly enforcing <= 2,000,000 TPM."""

    def __init__(self, max_tpm: int = 2_000_000, window_seconds: float = 60.0, clock: VirtualClock | None = None) -> None:
        if max_tpm <= 0 or max_tpm > 2_000_000:
            raise ValueError("max_tpm must be in (0, 2_000_000]")
        self.max_tpm = max_tpm
        self.window_seconds = window_seconds
        self.clock = clock or VirtualClock(virtual=False)
        self._events: deque[tuple[float, int]] = deque()
        self._lock = asyncio.Lock()
        self.peak_window_tokens: int = 0
        self.pacing_waits: int = 0
        self.total_waited_seconds: float = 0.0

    def _evict_expired(self, now: float) -> int:
        cutoff = now - self.window_seconds
        while self._events and self._events[0][0] <= cutoff:
            self._events.popleft()
        return sum(tokens for _, tokens in self._events)

    async def acquire(self, requested_tokens: int) -> float:
        if requested_tokens <= 0 or requested_tokens > self.max_tpm:
            raise ValueError(f"requested_tokens={requested_tokens} invalid for max_tpm={self.max_tpm}")
        waited = 0.0
        while True:
            async with self._lock:
                now = self.clock.now()
                used = self._evict_expired(now)
                if used + requested_tokens <= self.max_tpm:
                    self._events.append((now, requested_tokens))
                    new_used = used + requested_tokens
                    if new_used > self.peak_window_tokens:
                        self.peak_window_tokens = new_used
                    return waited
                oldest_ts = self._events[0][0]
                sleep_for = max(0.01, (oldest_ts + self.window_seconds) - now + 0.001)
                self.pacing_waits += 1
                self.total_waited_seconds += sleep_for
            waited += sleep_for
            await self.clock.sleep(sleep_for)

    async def reconcile(self, reserved_tokens: int, actual_tokens: int) -> None:
        """Release unused reserved tokens back to the sliding window when actual usage is smaller."""
        delta = actual_tokens - reserved_tokens
        if delta == 0:
            return
        async with self._lock:
            now = self.clock.now()
            self._events.append((now, delta))
            used = self._evict_expired(now)
            if used > self.peak_window_tokens:
                self.peak_window_tokens = used


def _urllib_post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> tuple[int, dict[str, str], dict[str, Any]]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, dict(resp.headers.items()), body
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8", errors="replace")
            headers_out = dict(exc.headers.items())
            code = exc.code
        finally:
            exc.close()
        parsed = json.loads(raw) if raw.strip().startswith("{") else {"error": raw}
        return code, headers_out, parsed


class BasetenSwarmClient:
    """Parallel Tessera worker burst dispatcher against Baseten Meta open-weight endpoints."""

    def __init__(
        self,
        endpoint_url: str = "https://inference.baseten.co/v1/chat/completions",
        api_key: str | None = None,
        max_tpm: int = 2_000_000,
        max_concurrency: int = 16,
        min_safe_lease_seconds: float = 15.0,
        clock: VirtualClock | None = None,
        transport: Callable[[str, dict[str, str], dict[str, Any]], tuple[int, dict[str, str], dict[str, Any]]] | None = None,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.api_key = api_key if api_key is not None else os.environ.get("BASETEN_API_KEY", "")
        self.clock = clock or VirtualClock(virtual=False)
        self.limiter = AsyncTokenBucket2M(max_tpm=max_tpm, clock=self.clock)
        self.sem = asyncio.Semaphore(max_concurrency)
        self.min_safe_lease_seconds = min_safe_lease_seconds
        self.latest_fence_by_task: dict[str, int] = {}
        self.transport = transport or _urllib_post_json

    def observe_fence(self, task_id: str, fencing_token: int) -> None:
        current = self.latest_fence_by_task.get(task_id, 0)
        if fencing_token > current:
            self.latest_fence_by_task[task_id] = fencing_token

    async def dispatch_claim(self, claim: FencedWorkerClaim, max_retries: int = 3) -> dict[str, Any]:
        """Dispatch one fenced claim with pre-flight lease check, <=2M TPM pacing and full attempt ledger."""
        known_fence = self.latest_fence_by_task.get(claim.task_id, claim.fencing_token)
        if claim.fencing_token < known_fence:
            return {
                "task_id": claim.task_id,
                "ok": False,
                "blocked_pre_flight": "stale_fencing_token",
                "tokens_burned": 0,
                "attempts": [],
            }
        self.observe_fence(claim.task_id, claim.fencing_token)
        if claim.remaining_lease_seconds < self.min_safe_lease_seconds:
            return {
                "task_id": claim.task_id,
                "ok": False,
                "blocked_pre_flight": "insufficient_remaining_lease_ttl",
                "tokens_burned": 0,
                "attempts": [],
            }

        reserved = claim.estimated_prompt_tokens + claim.max_completion_tokens
        attempts: list[dict[str, Any]] = []
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Api-Key {self.api_key}"

        for attempt_no in range(1, max_retries + 1):
            waited_s = await self.limiter.acquire(reserved)
            async with self.sem:
                payload = {
                    "model": claim.model,
                    "messages": [{"role": "user", "content": claim.prompt}],
                    "max_tokens": claim.max_completion_tokens,
                    "temperature": 0.1,
                }
                status, resp_headers, body = await asyncio.to_thread(
                    self.transport, self.endpoint_url, headers, payload
                )

            if status == 200:
                usage = body.get("usage", {})
                actual = int(usage.get("total_tokens", reserved))
                await self.limiter.reconcile(reserved, actual)
                attempts.append(
                    {
                        "attempt": attempt_no,
                        "http_status": 200,
                        "paced_wait_seconds": round(waited_s, 4),
                        "actual_tokens": actual,
                    }
                )
                return {
                    "task_id": claim.task_id,
                    "fencing_token": claim.fencing_token,
                    "ok": True,
                    "tokens_burned": sum(a.get("actual_tokens", 0) for a in attempts),
                    "attempts": attempts,
                    "content": body["choices"][0]["message"]["content"],
                }

            # Release unused token reservation on HTTP 429/503 and record failed attempt honestly!
            await self.limiter.reconcile(reserved, 0)
            retry_after = float(resp_headers.get("Retry-After", resp_headers.get("retry-after", 0.5 * (2 ** (attempt_no - 1)))))
            attempts.append(
                {
                    "attempt": attempt_no,
                    "http_status": status,
                    "paced_wait_seconds": round(waited_s, 4),
                    "retry_after_seconds": retry_after,
                    "actual_tokens": 0,
                }
            )
            if status in {429, 503} and attempt_no < max_retries:
                await self.clock.sleep(retry_after)
                continue
            break

        return {
            "task_id": claim.task_id,
            "fencing_token": claim.fencing_token,
            "ok": False,
            "tokens_burned": 0,
            "attempts": attempts,
        }

    async def dispatch_swarm(self, claims: list[FencedWorkerClaim]) -> list[dict[str, Any]]:
        return list(await asyncio.gather(*(self.dispatch_claim(c) for c in claims)))


def run_baseten_mock_swarm_verification() -> dict[str, Any]:
    """Verify <=2,000,000 TPM burst pacing, 429 Retry-After recovery and fenced lease safety against a local loopback server."""
    call_counter = {"count": 0, "transient_429_injected": 0}
    counter_lock = threading.Lock()

    class _MockBasetenHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            with counter_lock:
                call_counter["count"] += 1
                idx = call_counter["count"]
                # Inject one realistic HTTP 429 on call #3 to verify Retry-After + attempt preservation
                if idx == 3 and call_counter["transient_429_injected"] == 0:
                    call_counter["transient_429_injected"] = 1
                    self.send_response(429)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Retry-After", "1.25")
                    self.end_headers()
                    self.wfile.write(b'{"error":"rate_limit_spike"}')
                    return

            max_toks = int(body.get("max_tokens", 1000))
            actual_total = int(max_toks * 1.8)  # prompt + completion <= reserved
            resp = {
                "id": f"mock-baseten-{idx}",
                "model": body.get("model", "meta-llama/Llama-3.3-70B-Instruct"),
                "choices": [{"index": 0, "message": {"role": "assistant", "content": '{"verified":true}'}}],
                "usage": {"total_tokens": actual_total},
            }
            payload_bytes = json.dumps(resp).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload_bytes)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _MockBasetenHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        vclock = VirtualClock(virtual=True)
        client = BasetenSwarmClient(
            endpoint_url=f"http://127.0.0.1:{port}/v1/chat/completions",
            api_key="",
            max_tpm=2_000_000,
            max_concurrency=8,
            clock=vclock,
        )
        # Register task-stale as already fenced at token 5 so token 4 gets rejected pre-flight!
        client.observe_fence("TASK-STALE-FENCE", 5)

        # 12 valid claims reserving 220,000 tokens each = 2,640,000 tokens > 2,000,000 TPM ceiling!
        # Plus 1 stale-fence claim + 1 expiring-lease claim (both must burn 0 tokens).
        claims = [
            FencedWorkerClaim(
                task_id=f"TASK-SWARM-{i:02d}",
                fencing_token=1,
                remaining_lease_seconds=600.0,
                prompt=f"Audit public statute batch {i}",
                estimated_prompt_tokens=120_000,
                max_completion_tokens=100_000,
            )
            for i in range(1, 13)
        ] + [
            FencedWorkerClaim(
                task_id="TASK-STALE-FENCE",
                fencing_token=4,
                remaining_lease_seconds=600.0,
                prompt="Stale worker attempt",
                estimated_prompt_tokens=50_000,
                max_completion_tokens=50_000,
            ),
            FencedWorkerClaim(
                task_id="TASK-EXPIRING-LEASE",
                fencing_token=1,
                remaining_lease_seconds=4.0,
                prompt="Expiring worker attempt",
                estimated_prompt_tokens=50_000,
                max_completion_tokens=50_000,
            ),
        ]
        results = asyncio.run(client.dispatch_swarm(claims))
    finally:
        server.shutdown()
        server.server_close()

    succeeded = [r for r in results if r.get("ok")]
    pre_flight_blocked = [r for r in results if r.get("blocked_pre_flight")]
    retried = [r for r in succeeded if len(r["attempts"]) > 1]

    receipt = {
        "provider": "baseten",
        "mode": "local_verified",
        "live_credentials_present": bool(os.environ.get("BASETEN_API_KEY")),
        "max_tpm_ceiling": 2_000_000,
        "peak_sliding_window_tokens": client.limiter.peak_window_tokens,
        "respected_2m_tpm_ceiling": client.limiter.peak_window_tokens <= 2_000_000,
        "total_claims_submitted": len(claims),
        "succeeded_claims": len(succeeded),
        "pre_flight_fenced_or_ttl_blocked": len(pre_flight_blocked),
        "retried_429_preserved_in_ledger": len(retried) == 1 and retried[0]["attempts"][0]["http_status"] == 429,
        "pacing_waits_triggered": client.limiter.pacing_waits,
        "virtual_seconds_paced": round(client.limiter.total_waited_seconds, 3),
        "total_tokens_processed": sum(r["tokens_burned"] for r in succeeded),
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return receipt
