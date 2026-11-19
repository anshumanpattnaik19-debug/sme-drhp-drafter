"""RunPod endpoint setup (serve/runpod.py): pool choice and the usage-only worker settings, without calling RunPod."""
from argparse import Namespace

from serve.runpod import endpoint_body, pick_pools

CATALOG = [
    {"id": "NVIDIA L4", "name": "L4", "pool": "AMPERE_24", "manufacturer": "NVIDIA", "memory": 24, "price": {"serverless": 0.75}},
    {"id": "NVIDIA RTX A5000", "name": "RTX A5000", "pool": "AMPERE_24", "manufacturer": "NVIDIA", "memory": 24, "price": {"serverless": 0.75}},
    {"id": "NVIDIA GeForce RTX 4090", "name": "RTX 4090", "pool": "ADA_24", "manufacturer": "NVIDIA", "memory": 24, "price": {"serverless": 1.34}},
    {"id": "NVIDIA RTX A6000", "name": "RTX A6000", "pool": "AMPERE_48", "manufacturer": "NVIDIA", "memory": 48, "price": {"serverless": 1.22}},
    {"id": "NVIDIA L40S", "name": "L40S", "pool": "ADA_48_PRO", "manufacturer": "NVIDIA", "memory": 48, "price": {"serverless": 1.89}},
    {"id": "NVIDIA H100", "name": "H100", "pool": None, "manufacturer": "NVIDIA", "memory": 80, "price": {"serverless": None}},
]


def test_pick_pools_takes_cheapest_24_then_48():
    pools = pick_pools(CATALOG)
    assert [p[0] for p in pools] == ["AMPERE_24", "AMPERE_48"]
    assert pools[0][2] == 0.75 and set(pools[0][3]) == {"L4", "RTX A5000"}


def test_endpoint_has_no_always_on_worker_and_serves_the_app_model_name():
    body = endpoint_body(pick_pools(CATALOG), "user/sme-drhp-7b-lora", Namespace(name="sme-drhp-7b", idle=30))
    assert body["workers"] == {"min": 0, "max": 1, "idleTimeout": 30}
    assert body["env"]["MODEL_NAME"] == "Qwen/Qwen2.5-7B-Instruct"
    assert '"name": "sme-drhp-7b"' in body["env"]["LORA_MODULES"]
    assert body["env"]["HF_TOKEN"].startswith("{{ RUNPOD_SECRET_")          # the token itself is never in the body
    assert body["gpu"]["pools"] == ["AMPERE_24", "AMPERE_48"]
