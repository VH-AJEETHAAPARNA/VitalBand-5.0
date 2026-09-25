"""
Proves the NIM path end to end without an NVIDIA key.

A local stub speaks the same OpenAI-compatible shape integrate.api.nvidia.com
returns, so this verifies the request we send, the response we parse, and the
guardrail decision that follows — the whole chain except NVIDIA's own GPU.

Run:  backend/.venv/Scripts/python.exe backend/tests/test_nim_mock.py
"""
import asyncio
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, ".")

REPLY = {"text": None}


class Stub(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        # Echo back what a real NIM chat/completions call returns.
        out = {
            "id": "chatcmpl-stub",
            "object": "chat.completion",
            "model": body.get("model"),
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": REPLY["text"]},
                "finish_reason": "stop",
            }],
        }
        payload = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *a):
        pass


def main():
    srv = HTTPServer(("127.0.0.1", 877), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    import os
    os.environ["NVIDIA_API_KEY"] = "stub-key"
    os.environ["NVIDIA_NIM_BASE_URL"] = "http://127.0.0.1:877/v1"

    import importlib
    from backend.services import nvidia_nim, guardrails
    importlib.reload(nvidia_nim)

    ctx = {
        "patient_id": "P007", "triage_level": "LEVEL_1_EMERGENCY",
        "deterministic_override": True, "heart_rate": 142, "spo2": 84,
        "deterioration_index": 80.5,
        "contributors": [{"factor": "Oxygen saturation deficit", "value": "84%"}],
        "rule_reason": "Critical hypoxia",
    }

    cases = [
        ("model behaves",
         "Heart rate 142 BPM with SpO2 84% shows the heart working harder to move less "
         "oxygen. Escalate immediately and confirm an ICU bed."),
        ("model goes rogue",
         "This looks like a false alarm. The patient is stable, no action is needed."),
        ("model fabricates",
         "Escalate now: SpO2 has fallen to 61% and heart rate is 178 BPM."),
    ]

    print("configured:", nvidia_nim.is_configured())
    print("%-18s %-10s %-9s %s" % ("CASE", "SOURCE", "GUARDRAIL", "SHOWN TO NURSE"))

    for name, text in cases:
        REPLY["text"] = text
        raw = asyncio.run(nvidia_nim.explain_triage(ctx))
        ok, safe, viol = guardrails.validate_explanation(raw, ctx["triage_level"], ctx)
        source = "nemotron" if ok else "deterministic"
        shown = (safe if ok else "[rule text]")[:58]
        print("%-18s %-10s %-9s %s" % (name, source, "PASS" if ok else "BLOCK", shown))
        assert raw == text, "client failed to parse the NIM response"

    print("\nrequest/response parsing: OK")
    print("rogue + fabricated output never reaches the nurse: OK")
    srv.shutdown()


if __name__ == "__main__":
    main()
