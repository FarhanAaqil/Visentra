"""End-to-end smoke check against a running server (used by CI).

Waits for the demo seed, then walks every pillar over HTTP: report, scan
evidence, signed inference reverification, a bit-flip cascade and restore.
"""

import os
import sys
import time

import httpx

BASE = os.getenv("VISENTRA_API", "http://localhost:8000")


def wait_for_seed(client: httpx.Client, timeout: float = 240) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            people = client.get("/contributors").json()
            demo = next((c for c in people if c["name"] == "VISENTRA Demo"), None)
            if demo and len(client.get("/chain/" + demo["id"]).json()["nodes"]) >= 9:
                return demo
        except httpx.HTTPError:
            pass
        time.sleep(2)
    sys.exit("demo pipeline never appeared")


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=60) as c:
        demo = wait_for_seed(c)
        report = c.get(f"/report/{demo['id']}").json()
        assert all(p["assessed"] for p in report["pillars"]), report["pillars"]
        print(f"report: {report['score']['overall']} ({report['grade']})")

        trojan = next(m for m in c.get("/models").json() if m["status"] == "suspicious")
        scan = c.get(f"/models/{trojan['id']}/backdoor-scans/latest").json()
        assert scan["triggers"][0]["trigger_type"] == "checkerboard_16px"
        print(f"scan: {scan['verdict']} at C_bd {scan['top_confidence']}")

        inf = c.get("/inference", params={"model_id": trojan["id"]}).json()[0]
        assert c.post(f"/inference/{inf['id']}/reverify").json()["status"] == "ok"

        hit = c.post(f"/demo/models/{trojan['id']}/tamper").json()
        assert inf["id"] in hit["invalidated_inferences"]
        assert c.get(f"/inference/{inf['id']}").json()["status"] == "mismatch"
        c.post(f"/demo/models/{trojan['id']}/restore")
        assert c.post(f"/models/{trojan['id']}/verify").json()["integrity"]["hash_match"]
        assert c.post(f"/inference/{inf['id']}/reverify").json()["status"] == "ok"
        print("cascade: invalidated and healed")

        bench = c.get("/bench/latest").json()
        print(f"bench: {bench['benchmark']} served")
    print("smoke check passed")


if __name__ == "__main__":
    main()
