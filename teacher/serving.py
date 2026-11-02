"""vLLM server control for the Colab teacher stages (1, 2, 2b): pick the candidates for the GPU, start one, stop it.

    from teacher.serving import candidates, gpu_gb, serve, stop
    c = candidates(gpu_gb())['qwen3_32b_awq']
    p = serve(c['model'], c['args'])
    try: ...  finally: stop(p)

Every stage cell imports these, so any stage can run on its own in a fresh runtime (after stage 0).
"""
from __future__ import annotations

import subprocess
import time


def gpu_gb():
    import torch
    return torch.cuda.get_device_properties(0).total_memory / 2**30


def candidates(gpu_gb):
    """The two teachers of the screen. 32B AWQ is ~19 GB of weights and fits a 40 GB A100. 30B-A3B in BF16 is ~61 GB:
    on a 40 GB A100 use Qwen's FP8 checkpoint (~31 GB; vLLM runs FP8 weights on Ampere through Marlin kernels) with a
    shorter context."""
    return {
        "qwen3_32b_awq": dict(model="Qwen/Qwen3-32B-AWQ", args="--quantization awq_marlin --max-model-len 16384"),
        "qwen3_30b_a3b": (dict(model="Qwen/Qwen3-30B-A3B-Instruct-2507", args="--max-model-len 16384") if gpu_gb > 75 else
                          dict(model="Qwen/Qwen3-30B-A3B-Instruct-2507-FP8", args="--max-model-len 12288")),
    }


def stop(p):
    """Killing the 'vllm serve' wrapper alone leaves its engine process holding GPU memory, so the next model then fails
    to start with "Engine core initialization failed": kill the whole vLLM process tree."""
    p.kill()
    subprocess.run(["pkill", "-9", "-f", "[v]llm|[E]ngineCore"])
    time.sleep(20)
    used = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv"], capture_output=True, text=True).stdout
    print("GPU memory used after stop:", used.split()[-2:])


def serve(model, args, port=8000, log_dir="/content"):
    """Start `vllm serve` and wait (up to 30 minutes, for the download and load) until it answers /v1/models."""
    import httpx
    log_path = f"{log_dir}/vllm_{port}.log"
    log = open(log_path, "w")
    p = subprocess.Popen(f"vllm serve {model} --port {port} --gpu-memory-utilization 0.92 --served-model-name {model} {args}".split(),
                         stdout=log, stderr=log)
    for _ in range(180):
        try:
            if httpx.get(f"http://localhost:{port}/v1/models", timeout=2).status_code == 200:
                return p
        except Exception:  # noqa: BLE001 - the server is still starting
            pass
        time.sleep(10)
    stop(p)
    raise RuntimeError(open(log_path).read()[-3000:])
