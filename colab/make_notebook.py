"""Writes colab/sme_drhp_colab.ipynb (kept as a script so the notebook is reviewable as code) and the Drive package.

    python colab/make_notebook.py            # notebook + colab/sme_drhp_colab.zip (code + teacher jobs, no corpus)

Stages (PLAN.md sections 9-11). GPU stages run on Colab; building the rows runs on the laptop in between, because
it needs the 62,947 segmented train units (precedents, MinHash). Files move through MyDrive/sme_drhp/, which
Google Drive for desktop syncs to the laptop.
"""
import json
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
cells = []


def md(s):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": s.strip("\n")})


def code(s):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s.strip("\n")})


md("""
# SME DRHP drafter: teacher extraction and QLoRA fine-tuning (Colab)

| stage | GPU | what it does | writes to `MyDrive/sme_drhp/` |
|---|---|---|---|
| 0 | any | unzip the package, install | – |
| 1 | A100 | **teacher screen**: two candidate teachers on 30 units | `screen/responses_<tag>.jsonl`, `screen/SCREEN_REPORT.md` |
| 2 | A100 | **full teacher extraction**, 2,062 calls, resumable | `work/teacher_responses.jsonl` |
| – | laptop | `python -m data.build rows` (gates, router, distractors, precedents, MinHash) | `out/train.jsonl`, `out/test.jsonl` |
| 3 | L4 | **baselines** B0/B1 on the test rows | `runs/B0`, `runs/B1` |
| 4 | L4 | **QLoRA runs** A and B (+ ablation 1, seeds) | `runs/<run>/adapter`, `runs/<run>/predictions_test.jsonl` |
| 5 | L4 | **decoding re-test + DPO against looping** (added 4 Nov 2026) | `runs/A/decode_test/`, `out/dpo_pairs.jsonl`, `runs/A_dpo/adapter` |

Every stage is resumable: rerun a cell after a disconnect and it continues. Check the per-GPU unit rate in the
Resources panel before the first run, and disconnect the runtime when a stage finishes.
""")

md("## Stage 0: setup")
code("""
from google.colab import drive
drive.mount('/content/drive')
import os, subprocess, sys, json, time
DRIVE = '/content/drive/MyDrive/sme_drhp'
os.makedirs(DRIVE, exist_ok=True)
for d in ('screen', 'work', 'out', 'runs'):
    os.makedirs(f'{DRIVE}/{d}', exist_ok=True)
PKG = f'{DRIVE}/sme_drhp_colab.zip'
if not os.path.exists(PKG):
    # not on Drive yet: pick sme_drhp_drafter/colab/sme_drhp_colab.zip from your laptop; it is saved to Drive for next time
    from google.colab import files
    up = files.upload()
    name = next(iter(up))
    open(PKG, 'wb').write(up[name])
    print(f'saved {name} -> {PKG}')
!rm -rf /content/sme && mkdir -p /content/sme && unzip -q -o {PKG} -d /content/sme
assert os.path.exists('/content/sme/teacher/driver.py'), 'package did not unzip'
%cd /content/sme
sys.path.insert(0, '/content/sme')
!nvidia-smi --query-gpu=name,memory.total --format=csv
""")
code("""
# teacher serving (latest vLLM: Colab runs Python 3.13, which older pinned versions do not support)
# uv resolves and downloads far faster than pip and shows progress (pip -q can sit silently for 10+ minutes)
!pip install -q uv
!uv pip install --system "vllm==0.32.0" "httpx>=0.27" fastapi "pydantic>=2"   # installs on Colab (Python 3.13), 1 Nov 2026
!pip show vllm 2>/dev/null | head -2
""")

md("""
## Stage 1: teacher screen (A100)

Both candidates from PLAN.md read the same 30 units (`trainset/screen/screen_jobs.jsonl`). Upload your labels first:
fill `reviewer_labels.xlsx` (10 units) on the laptop, run `python -m teacher.label_sheet read --xlsx ...`, and copy
`reviewer_labels.json` to `MyDrive/sme_drhp/screen/`. Pass rule: precision >= 95% and coverage >= 85%.
""")
code("""
import os, sys, subprocess, json, time
DRIVE = '/content/drive/MyDrive/sme_drhp'     # this cell also runs alone in a fresh runtime, so set paths here
%cd /content/sme
sys.path.insert(0, '/content/sme')
from teacher.serving import candidates, gpu_gb, serve, stop   # serve/stop kill the whole vLLM tree between models
from teacher.driver import run
GPU_GB = gpu_gb()
CANDIDATES = candidates(GPU_GB)
print(f'GPU memory {GPU_GB:.0f} GB ->', {k: v['model'] for k, v in CANDIDATES.items()})
jobs = [json.loads(l) for l in open('trainset/screen/screen_jobs.jsonl', encoding='utf-8')]
for tag, c in CANDIDATES.items():
    out = f'{DRIVE}/screen/responses_{tag}.jsonl'
    p = serve(c['model'], c['args'])
    try:
        print(tag, run(jobs, out, 'http://localhost:8000/v1', c['model']))
    finally:
        stop(p)
""")
code("""
labels = f'{DRIVE}/screen/reviewer_labels.json'
lab = f'--labels {labels}' if os.path.exists(labels) else ''
!python -m teacher.screen score --responses {DRIVE}/screen/responses_qwen3_32b_awq.jsonl {DRIVE}/screen/responses_qwen3_30b_a3b.jsonl {lab}
!cp trainset/screen/SCREEN_REPORT.md {DRIVE}/screen/
""")

md("""
## Stage 2: full teacher extraction (resumable)

Set `TEACHER` to the candidate that passed the screen. 2,062 calls; rerun the cell after a disconnect and it skips
the units already answered. Then, on the laptop: `python -m data.build rows --responses <Drive>/work/teacher_responses.jsonl`
and copy `trainset/out/*.jsonl` to `MyDrive/sme_drhp/out/`.
""")
TEACHER_CELL = """
import os, sys, json
DRIVE = '/content/drive/MyDrive/sme_drhp'
%cd /content/sme
sys.path.insert(0, '/content/sme')
from teacher.serving import candidates, gpu_gb, serve, stop
from teacher.driver import run
TEACHER = 'qwen3_32b_awq'          # the candidate that passed SCREEN_REPORT.md (precision >= 95%, coverage >= 85%)
c = candidates(gpu_gb())[TEACHER]
jobs = [json.loads(l) for l in open('trainset/work/{jobs}', encoding='utf-8')]
p = serve(c['model'], c['args'])
try:
    print(run(jobs, f'{{DRIVE}}/work/{out}', 'http://localhost:8000/v1', c['model']))
finally:
    stop(p)
"""
code(TEACHER_CELL.format(jobs="teacher_jobs.jsonl", out="teacher_responses.jsonl"))

md("""
## Stage 2b: gap-fill (A100, about 500 short calls)

A second teacher pass for drafting units that failed the coverage gate: the prompt lists the figures, dates and names
the first pass missed (`trainset/work/gapfill_jobs.jsonl`, made on the laptop with `python -m teacher.gapfill jobs`).
Resumable like stage 2. Then, on the laptop: `python -m teacher.gapfill merge ...` and `python -m data.build rows`
on the merged responses (TRAINING.md).
""")
code(TEACHER_CELL.format(jobs="gapfill_jobs.jsonl", out="gapfill_responses.jsonl"))

md("""
## Stage 3-4: baselines and QLoRA (L4)

Student `Qwen/Qwen2.5-7B-Instruct`, 4-bit QLoRA with Unsloth, loss on the assistant turn only, `max_seq_len` 6,144.
Runs (PLAN.md 7.7): **A** r16 / lr 2e-4 / all linear layers / 2 epochs; **B** r64 / lr 1e-4; **C** r32 / lr 2e-4 /
3 epochs / drafting rows twice (added 1 Nov 2026: run A did not beat the base model on drafting); **A2** = run A on
`train_nopage.jsonl` / `test_nopage.jsonl`, page numbers cut from cross-references (added 3 Nov 2026: run A loops and
invents page numbers; built by `python -m data.nopage trainset/out`); **ablation1** = best
config on `train_no_distractors.jsonl`; **seed2/seed3** = best config with other seeds. Each team member runs one.
A configuration counts as better only if its **held-out loss** on the test drafts beats the base model's (cell after
training); run the seed and ablation runs only once a configuration passes.
Set a `WANDB_API_KEY` Colab secret to log to Weights & Biases.
""")
code("""
!pip install -q uv
!uv pip install --system "unsloth" "trl>=0.19" "peft" "bitsandbytes" "datasets" "wandb"
# torchvision on the Colab image is built against Pillow 11.3.0; a newer Pillow breaks the Unsloth import
!uv pip install --system --reinstall "pillow==11.3.0"
!pip show unsloth trl torch vllm pillow 2>/dev/null | grep -E '^(Name|Version)'
# now Runtime > Restart session, then run stage 0 again and continue from the next cell
""")
code("""
RUNS = {
    'A':         dict(r=16, alpha=32, lr=2e-4, epochs=2, data='train.jsonl', seed=3407),
    'B':         dict(r=64, alpha=64, lr=1e-4, epochs=2, data='train.jsonl', seed=3407),
    'C':         dict(r=32, alpha=64, lr=2e-4, epochs=3, data='train.jsonl', seed=3407, draft_weight=2),
    'A2':        dict(r=16, alpha=32, lr=2e-4, epochs=2, data='train_nopage.jsonl', test='test_nopage.jsonl', seed=3407),
    'ablation1': dict(r=16, alpha=32, lr=2e-4, epochs=2, data='train_no_distractors.jsonl', seed=3407),
    'seed2':     dict(r=16, alpha=32, lr=2e-4, epochs=2, data='train.jsonl', seed=11),
    'seed3':     dict(r=16, alpha=32, lr=2e-4, epochs=2, data='train.jsonl', seed=23),
    'A_dpo':     dict(r=16, alpha=32, lr=1e-5, epochs=2, data='dpo_pairs.jsonl', seed=3407, method='dpo'),  # stage 5: trained by the DPO cell (22), not cell 15
    # v2 (14 Nov 2026): the Q&A skill with guardrails added (data/qa.py); run A's settings, then DPO as for A_dpo
    'A_qa':      dict(r=16, alpha=32, lr=2e-4, epochs=2, data='train_v2.jsonl', test='test_v2.jsonl', seed=3407),
    'A_qa_dpo':  dict(r=16, alpha=32, lr=1e-5, epochs=2, data='dpo_pairs_A_qa.jsonl', test='test_v2.jsonl', seed=3407, method='dpo'),  # cells 21-22 with SRC = 'A_qa'
}
RUN = 'A'                       # change per team member
TEST = RUNS[RUN].get('test', 'test.jsonl')    # the test file cells 16-18 read
BASE = 'Qwen/Qwen2.5-7B-Instruct'
MAX_SEQ = 6144
cfg = RUNS[RUN]
out_dir = f'{DRIVE}/runs/{RUN}'
os.makedirs(out_dir, exist_ok=True)
try:
    from google.colab import userdata
    os.environ['WANDB_API_KEY'] = userdata.get('WANDB_API_KEY'); report = 'wandb'
except Exception:
    report = 'none'
""")
code("""
# CELL 15 - TRAINING (about 75 min on an L4)
assert 'out_dir' in globals(), 'run stage 0 (cell 3) and the RUNS cell (cell 14) first'
assert cfg.get('method') != 'dpo', f'{RUN} is trained by the stage 5 DPO cell (22), not here'
from unsloth import FastLanguageModel
from unsloth.chat_templates import train_on_responses_only
from datasets import Dataset
from trl import SFTTrainer, SFTConfig

model, tok = FastLanguageModel.from_pretrained(BASE, max_seq_length=MAX_SEQ, load_in_4bit=True)
model = FastLanguageModel.get_peft_model(model, r=cfg['r'], lora_alpha=cfg['alpha'], lora_dropout=0.0,
    target_modules=['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj'],
    use_gradient_checkpointing='unsloth', random_state=cfg['seed'])
rows = [json.loads(l) for l in open(f"{DRIVE}/out/{cfg['data']}", encoding='utf-8')]
rows += [r for r in rows if r['metadata']['skill'] == 'drafting'] * (cfg.get('draft_weight', 1) - 1)
ds = Dataset.from_list([{'text': tok.apply_chat_template(r['messages'], tokenize=False)} for r in rows])
# checkpoints on Drive so a disconnect can resume; TRL >= 0.20 renamed max_seq_length to max_length
ckpt_dir = f'{out_dir}/ckpt'
seq_kw = 'max_length' if 'max_length' in SFTConfig.__dataclass_fields__ else 'max_seq_length'
trainer = SFTTrainer(model=model, processing_class=tok, train_dataset=ds,
    args=SFTConfig(output_dir=ckpt_dir, dataset_text_field='text', packing=False, **{seq_kw: MAX_SEQ},
                   per_device_train_batch_size=1, gradient_accumulation_steps=16, num_train_epochs=cfg['epochs'],
                   learning_rate=cfg['lr'], lr_scheduler_type='cosine', warmup_steps=6, logging_steps=5,
                   save_strategy='steps', save_steps=25, save_total_limit=2, bf16=True, optim='adamw_8bit',
                   seed=cfg['seed'], report_to=report, run_name=f'sme-drhp-{RUN}'))
trainer = train_on_responses_only(trainer, instruction_part='<|im_start|>user\\n', response_part='<|im_start|>assistant\\n')
last = None
if os.path.isdir(ckpt_dir):
    ck = sorted((d for d in os.listdir(ckpt_dir) if d.startswith('checkpoint-')), key=lambda d: int(d.split('-')[1]))
    last = f'{ckpt_dir}/{ck[-1]}' if ck else None
print('rows', len(ds), '| resume from', last)
trainer.train(resume_from_checkpoint=last)
model.save_pretrained(f'{out_dir}/adapter'); tok.save_pretrained(f'{out_dir}/adapter')
json.dump({'run': RUN, **cfg, 'base': BASE, 'log': trainer.state.log_history[-5:]}, open(f'{out_dir}/train_summary.json', 'w'), indent=1)
""")
code("""
# CELL 16 - HELD-OUT LOSS
# held-out loss on the test rows, adapter on and off: the yes/no measure for a configuration (no generation, so
# decoding loops cannot distort it). Runs straight after training, or alone: Restart session, stage 0, the RUNS cell,
# then this cell (it loads runs/<RUN>/adapter). About 5 minutes.
assert 'out_dir' in globals(), 'run stage 0 (cell 3) and the RUNS cell (cell 14) first'
import torch
if 'model' not in globals():
    assert os.path.isfile(f'{out_dir}/adapter/adapter_config.json'), f'no adapter in {out_dir}: train run {RUN} first (cell 15)'
    import importlib.util
    assert importlib.util.find_spec('unsloth'), 'Unsloth not installed on this machine: run cells 4 and 13, Restart session, stage 0, the RUNS cell, then this cell'
    from unsloth import FastLanguageModel
    model, tok = FastLanguageModel.from_pretrained(f'{out_dir}/adapter', max_seq_length=MAX_SEQ, load_in_4bit=True)
model.eval()
test = [json.loads(l) for l in open(f'{DRIVE}/out/{TEST}', encoding='utf-8')]

def nll(r):
    n = len(tok(tok.apply_chat_template(r['messages'][:-1], tokenize=False, add_generation_prompt=True)).input_ids)
    ids = tok(tok.apply_chat_template(r['messages'], tokenize=False), return_tensors='pt').input_ids.cuda()
    lab = ids.clone(); lab[:, :n] = -100
    with torch.no_grad():
        return model(input_ids=ids, labels=lab).loss.item() * (ids.shape[1] - n), ids.shape[1] - n

def mean_loss(rows):
    s = [nll(r) for r in rows]
    return sum(a for a, _ in s) / sum(b for _, b in s)

res = {}
for sk in [s for s in ('drafting', 'extraction', 'qa') if any(r['metadata']['skill'] == s for r in test)]:
    rs = [r for r in test if r['metadata']['skill'] == sk]
    res[sk] = {'adapter': mean_loss(rs)}
    with model.disable_adapter():
        res[sk]['base'] = mean_loss(rs)
    print(f"{sk:10s} held-out loss  {RUN} {res[sk]['adapter']:.3f}  |  base {res[sk]['base']:.3f}  ({len(rs)} rows)")
json.dump(res, open(f'{out_dir}/heldout_loss.json', 'w'), indent=1)
""")
code("""
# CELL 17 - PREDICTIONS (vLLM): the run's main result, after every training run
# predictions on the test rows (B0 = base model with no adapter; set ADAPTER=None)
# run in a fresh runtime (Restart session, stage 0, the RUNS cell, then this one): the training model would
# otherwise still hold the L4's memory when vLLM starts
assert 'out_dir' in globals(), 'run stage 0 (cell 3) and the RUNS cell (cell 14) first'
import torch
assert torch.cuda.is_bf16_supported(), f'{torch.cuda.get_device_name()}: needs an L4 or A100 (a T4 has no bf16 and too little memory)'
free, total = torch.cuda.mem_get_info()   # whole GPU: vLLM's engine runs in another process, which memory_allocated misses
assert free > 0.8 * total, f'{(total - free) / 2**30:.1f} GB of the GPU is in use (a model from an earlier cell): Restart session, stage 0, the RUNS cell, then this cell'
os.environ.setdefault('VLLM_ENGINE_READY_TIMEOUT_S', '3600')   # vLLM loads the 15 GB bf16 weights in a child process: no progress bar, 600 s default
try:
    from google.colab import userdata                            # optional HF_TOKEN secret: faster, un-throttled downloads
    os.environ.setdefault('HF_TOKEN', userdata.get('HF_TOKEN'))
except Exception:
    pass
from huggingface_hub import snapshot_download
snapshot_download(BASE, allow_patterns=['*.json', '*.safetensors', '*.txt'])   # visible download first; instant once cached
from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest
from transformers import AutoTokenizer
from data.prompts import trim_repeats      # needs the package from 1 Nov 2026 or later (stage 0 zip)
tok = AutoTokenizer.from_pretrained(BASE)
BASELINE = False                         # True for baseline B0 (base model, no adapter)
TEMP = 0                                 # drafting only: 0 = greedy; 0.3 = low-temperature sampling (run A loops under greedy)
FREQ = 0.3                               # drafting only: frequency penalty, chosen by the stage 5 decoding re-test; 0 = off (writes _f03 when on)
REP = 1.0                                # drafting only: repetition penalty, 1.0 = off (writes _rp110 for 1.1)
ADAPTER = None if BASELINE else f'{out_dir}/adapter'
pred_dir = out_dir if ADAPTER else f'{DRIVE}/runs/B0'
tag = (('' if TEMP == 0 else f'_t{TEMP:g}'.replace('.', '')) + ('' if FREQ == 0 else f'_f{round(FREQ * 10):02d}')
       + ('' if REP == 1.0 else f'_rp{round(REP * 100)}'))
os.makedirs(pred_dir, exist_ok=True)
llm = LLM(BASE, enable_lora=ADAPTER is not None, max_lora_rank=64, max_model_len=MAX_SEQ, gpu_memory_utilization=0.9)
rows = [json.loads(l) for l in open(f'{DRIVE}/out/{TEST}', encoding='utf-8')]
prompts = [tok.apply_chat_template(r['messages'][:-1], tokenize=False, add_generation_prompt=True) for r in rows]
# caps from the target lengths (99th percentile: drafting about 2,100 tokens, extraction about 2,350; Q&A answers are short)
cap = {'drafting': 2200, 'extraction': 3000, 'qa': 600}
# extraction and Q&A stay greedy (values are copied exactly); a fixed seed makes a sampled run repeatable
params = [SamplingParams(temperature=TEMP, top_p=0.9 if TEMP else 1.0, seed=1234, frequency_penalty=FREQ,
                         repetition_penalty=REP, max_tokens=cap['drafting'])
          if r['metadata']['skill'] == 'drafting' else
          SamplingParams(temperature=0, max_tokens=cap[r['metadata']['skill']]) for r in rows]
outs = llm.generate(prompts, params, lora_request=LoRARequest('a', 1, ADAPTER) if ADAPTER else None)
n_cut = n_cap = 0
with open(f'{pred_dir}/predictions_test{tag}.jsonl', 'w', encoding='utf-8') as fh:
    for r, o in zip(rows, outs):
        raw, finish = o.outputs[0].text, o.outputs[0].finish_reason
        pred, cut = trim_repeats(raw) if r['metadata']['skill'] == 'drafting' else (raw, False)
        n_cut += cut; n_cap += finish == 'length'
        fh.write(json.dumps({'id': r['id'], 'metadata': r['metadata'], 'prediction': pred, 'raw': raw,
                             'finish': finish, 'loop_trimmed': cut}, ensure_ascii=False) + '\\n')
print(f'predictions_test{tag}.jsonl written: {len(rows)} rows, {n_cap} hit the cap, {n_cut} drafts trimmed at a loop')
""")
code(r"""
# CELL 18 - OPTIONAL 4-bit check, done for run A on 2 Nov 2026. Not part of a normal run: skip it.
# 4-bit check: do the drafts that looped under vLLM (bf16 base) still loop on the 4-bit base the adapter was
# trained on? (vLLM 0.32 cannot load bitsandbytes, so this uses Unsloth.) Answers: serving mismatch or training problem.
# Self-contained, about 10 minutes on an L4. In a fresh runtime: stage 0, then the Unsloth install (cell 13),
# Runtime > Restart session, stage 0 again, then THIS cell. The RUNS cell is not needed.
CHECK_4BIT = False                       # set True only to repeat the 4-bit check
assert CHECK_4BIT, 'cell 18 is the optional 4-bit check and is off: for predictions run cell 17 (PREDICTIONS) instead'
import os, sys, json, importlib.util
import torch

CHECK = 'A'          # run whose greedy vLLM predictions are re-checked (run A is the reference case; 'A2' and 'B' also work)
N = 20               # looped / capped drafts to regenerate
MAX_SEQ = 6144
DRIVE = '/content/drive/MyDrive/sme_drhp'

assert os.path.isfile('/content/sme/data/prompts.py'), 'package not unzipped: run stage 0 first'
if '/content/sme' not in sys.path:
    sys.path.insert(0, '/content/sme')
assert importlib.util.find_spec('unsloth'), 'Unsloth not installed: run cell 13, Restart session, stage 0, then this cell'
free, total = torch.cuda.mem_get_info()   # whole GPU: vLLM's engine runs in another process, which memory_allocated misses
assert free > 0.8 * total, f'{(total - free) / 2**30:.1f} GB of the GPU is in use (a model from an earlier cell): Restart session, stage 0, then this cell'

run_dir = f'{DRIVE}/runs/{CHECK}'
test_file = (globals().get('RUNS', {}).get(CHECK, {}).get('test')
             or {'A2': 'test_nopage.jsonl'}.get(CHECK, 'test.jsonl'))
vl_path = f'{run_dir}/predictions_test.jsonl'
assert os.path.isfile(f'{run_dir}/adapter/adapter_config.json'), f'no adapter in {run_dir}/adapter'
assert os.path.getsize(vl_path) > 0, f'{vl_path} missing or empty: run the vLLM predictions cell for {CHECK} first'

from unsloth import FastLanguageModel          # import before transformers
from data.prompts import trim_repeats

model, tok = FastLanguageModel.from_pretrained(f'{run_dir}/adapter', max_seq_length=MAX_SEQ, load_in_4bit=True)
FastLanguageModel.for_inference(model)
tok.padding_side = 'left'
stop_ids = [tok.convert_tokens_to_ids(t) for t in ('<|im_end|>', '<|endoftext|>')]

vl = {p['id']: p for p in map(json.loads, open(vl_path, encoding='utf-8'))}
rows = [r for r in map(json.loads, open(f'{DRIVE}/out/{test_file}', encoding='utf-8'))
        if r['metadata']['skill'] == 'drafting' and r['id'] in vl
        and (vl[r['id']]['loop_trimmed'] or vl[r['id']]['finish'] == 'length')][:N]
assert rows, f'no looped or capped drafts in {vl_path}'
print(f'run {CHECK} | {test_file} | re-generating {len(rows)} drafts that looped or hit the cap under vLLM')

out_path = f'{run_dir}/predictions_test_q4_hf.jsonl'
n_cut = n_cap = n_same = 0
with open(out_path, 'w', encoding='utf-8') as fh:
    for i in range(0, len(rows), 10):
        batch = rows[i:i + 10]
        enc = tok([tok.apply_chat_template(r['messages'][:-1], tokenize=False, add_generation_prompt=True) for r in batch],
                  return_tensors='pt', padding=True, add_special_tokens=False).to('cuda')
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=2200, do_sample=False, use_cache=True,
                                 eos_token_id=stop_ids, pad_token_id=tok.pad_token_id)
        for r, g in zip(batch, gen[:, enc.input_ids.shape[1]:].tolist()):
            finish = 'stop' if set(stop_ids) & set(g) else 'length'
            raw = tok.decode(g, skip_special_tokens=True)
            pred, cut = trim_repeats(raw)
            same = raw.strip()[:300] == vl[r['id']]['raw'].strip()[:300]
            n_cut += cut; n_cap += finish == 'length'; n_same += same
            fh.write(json.dumps({'id': r['id'], 'metadata': r['metadata'], 'prediction': pred, 'raw': raw,
                                 'finish': finish, 'loop_trimmed': cut}, ensure_ascii=False) + '\n')
            print(f"  {r['id'][:42]:42s} {finish:6s} loop={str(bool(cut)):5s} same_start={same}")
        fh.flush()
        print(f'  {min(i + 10, len(rows))}/{len(rows)} done')

n = len(rows)
still = sum(1 for p in map(json.loads, open(out_path, encoding='utf-8')) if p['finish'] == 'length' or p['loop_trimmed'])
verdict = ('training-side: the adapter loops on its own 4-bit base too; fix the run (fewer epochs / lower lr / data)'
           if still >= n / 2 else
           'serving-side: the loops mostly vanish on the 4-bit base; serve on the base the adapter was trained on')
summary = {'run': CHECK, 'test': test_file, 'drafts': n, 'hit_cap': n_cap, 'loop_trimmed': n_cut,
           'still_looping_or_capped': still, 'same_start_as_vllm': n_same, 'verdict': verdict}
json.dump(summary, open(f'{run_dir}/q4_check.json', 'w'), indent=1)
print(f'\n4-bit base, {n} drafts that looped on the bf16 base: {n_cap} hit the cap, {n_cut} trimmed at a loop, '
      f'{n_same} start the same as the vLLM draft\nverdict: {verdict}\nwritten: {out_path}, {run_dir}/q4_check.json')
""")

md(r"""
## Stage 5: decoding re-test and DPO against looping (added 4 Nov 2026)

The 4-bit check (cell 18, run 4 Nov) showed the looping is training-side: adapter A loops on the 4-bit base it was
trained on (11 of 20 drafts hit the cap, 8 loop). Analysis of the predictions: loops are mostly repeated boilerplate
sentences starting mid-draft, with the same rate for runs A and B and no dependence on fact count, distractors, prompt
length, precedent or table-like gold: greedy decoding degenerating on high-entropy targets, not a data or
hyperparameter problem. The `predictions_test_merged*` files are invalid (merging a 4-bit-trained adapter into bf16
weights broke the model), so penalties were never actually tested.

Order: (1) **decoding re-test** on the unmerged adapter through vLLM's LoRA path, with stop-on-loop (latency) and
presence / frequency / repetition penalties; (2) **DPO pairs**: adapter A drafts 400 train prompts, looped drafts are
`rejected`, the gold sub-section `chosen`; (3) **DPO** on top of adapter A with a frozen copy of A as the reference
(TRL `ref_adapter_name`); (4) rerun the held-out loss, predictions and decoding re-test with `A_dpo`. The label-mask
check (last cell) confirms `<|im_end|>` was inside the SFT loss. Cells 20-21 need the vLLM runtime (stage 0, cell 4);
cells 22-23 the Unsloth runtime (stage 0, cell 13, Restart session, stage 0).
""")
code(r'''
# CELL 20 - DECODING RE-TEST (vLLM, about 25 min)
# Decoding re-test on the UNMERGED adapter (the merged / rp105 prediction files are invalid: merging a 4-bit-trained
# adapter into bf16 weights broke the model). On the 89 drafting test rows it compares greedy with stop-on-loop against
# presence, frequency and repetition penalties, all through vLLM's LoRA path. Fresh runtime: stage 0, the vLLM install
# (cell 4), then this cell. About 25 minutes on an L4. Rerun with CHECK = 'A_dpo' after the DPO cell.
import os, sys, json, re, time
import torch

DRIVE = '/content/drive/MyDrive/sme_drhp'
CHECK = 'A_dpo'                    # adapter under test: 'A', 'B', 'A2' (reads test_nopage.jsonl) or 'A_dpo'
BASE = 'Qwen/Qwen2.5-7B-Instruct'
MAX_SEQ, CAP = 6144, 2200
CONFIGS = {     # name: (sampling kwargs, chunk): chunk = CAP is one shot; a smaller chunk stops at the first loop
    'greedy_loopstop': (dict(temperature=0), 384),
    'frequency03':     (dict(temperature=0, frequency_penalty=0.3), CAP),
    'frequency05':     (dict(temperature=0, frequency_penalty=0.5), CAP),
}

assert os.path.isfile('/content/sme/data/prompts.py'), 'package not unzipped: run stage 0 first'
if '/content/sme' not in sys.path:
    sys.path.insert(0, '/content/sme')
free, total = torch.cuda.mem_get_info()   # whole GPU: vLLM's engine runs in another process, which memory_allocated misses
assert free > 0.8 * total, f'{(total - free) / 2**30:.1f} GB of the GPU is in use (a model from an earlier cell): Restart session, stage 0, cell 4, then this cell'
import os
os.environ.setdefault('VLLM_ENGINE_READY_TIMEOUT_S', '3600')   # vLLM loads the 15 GB bf16 weights in a child process: no progress bar, 600 s default
try:
    from google.colab import userdata                            # optional HF_TOKEN secret: faster, un-throttled downloads
    os.environ.setdefault('HF_TOKEN', userdata.get('HF_TOKEN'))
except Exception:
    pass
from huggingface_hub import snapshot_download
snapshot_download(BASE, allow_patterns=['*.json', '*.safetensors', '*.txt'])   # visible download first; instant once cached
from vllm import LLM, SamplingParams
from vllm.inputs import TokensPrompt
from vllm.lora.request import LoRARequest
from transformers import AutoTokenizer
from data.prompts import trim_repeats

test_file = 'test_nopage.jsonl' if CHECK == 'A2' else 'test.jsonl'
adapter = f'{DRIVE}/runs/{CHECK}/adapter'
assert os.path.isfile(f'{adapter}/adapter_config.json'), f'no adapter at {adapter}'
out_dir = f'{DRIVE}/runs/{CHECK}/decode_test'
os.makedirs(out_dir, exist_ok=True)
tok = AutoTokenizer.from_pretrained(BASE)
rows = [r for r in map(json.loads, open(f'{DRIVE}/out/{test_file}', encoding='utf-8')) if r['metadata']['skill'] == 'drafting']
prompt_ids = [tok(tok.apply_chat_template(r['messages'][:-1], tokenize=False, add_generation_prompt=True),
                  add_special_tokens=False).input_ids for r in rows]
llm = LLM(BASE, enable_lora=True, max_lora_rank=64, max_model_len=MAX_SEQ, gpu_memory_utilization=0.9)
lora = LoRARequest('a', 1, adapter)


def generate(prompt_ids, kwargs, chunk, cap=CAP):
    """Rounds of `chunk` tokens per draft; a draft ends at <|im_end|>, at the cap, or (chunk < cap) at the first loop
    trim_repeats finds, so a loop costs one round instead of the whole cap. Penalties see only the current round."""
    state = [{'ids': list(p), 'out': [], 'done': None} for p in prompt_ids]
    while True:
        live = [i for i, s in enumerate(state) if s['done'] is None]
        if not live:
            return state
        prompts = [TokensPrompt(prompt_token_ids=state[i]['ids'] + state[i]['out']) for i in live]
        params = [SamplingParams(max_tokens=min(chunk, cap - len(state[i]['out'])), **kwargs) for i in live]
        outs = llm.generate(prompts, params, lora_request=lora, use_tqdm=False)
        for i, o in zip(live, outs):
            s = state[i]
            s['out'] += list(o.outputs[0].token_ids)
            _, cut = trim_repeats(tok.decode(s['out'], skip_special_tokens=True))
            if cut:
                s['done'] = 'loop'
            elif o.outputs[0].finish_reason == 'stop':
                s['done'] = 'stop'
            elif len(s['out']) >= cap:
                s['done'] = 'length'


NUM = re.compile(r'\d[\d,]*(?:\.\d+)?')
def nums(t):
    return {n.replace(',', '').rstrip('.') for n in NUM.findall(t) if len(n.replace(',', '')) >= 2}

def facts_of(user):
    m = re.search(r'^FACTS: (\[.*?\])\s*$', user, re.M)
    try:
        return [str(f['value']) for f in json.loads(m.group(1))]
    except Exception:
        return []

summary = {}
print(f'adapter {CHECK} | {len(rows)} drafting rows | {test_file}')
print(f"{'config':16s} {'loop%':>6s} {'cap%':>5s} {'len/gold':>8s} {'facts used':>10s} {'unsupported#':>12s} {'s/draft':>8s}")
for name, (kwargs, chunk) in CONFIGS.items():
    t0 = time.time()
    state = generate(prompt_ids, kwargs, chunk)
    secs = (time.time() - t0) / len(rows)
    n_loop = n_cap = 0; lr = fu = hal = 0.0
    with open(f'{out_dir}/{name}.jsonl', 'w', encoding='utf-8') as fh:
        for r, s in zip(rows, state):
            raw = tok.decode(s['out'], skip_special_tokens=True)
            pred, cut = trim_repeats(raw)
            gold = r['messages'][-1]['content']; user = r['messages'][1]['content']
            loop = cut or s['done'] == 'loop'; n_loop += loop; n_cap += s['done'] == 'length'
            lr += len(pred) / max(1, len(gold))
            vals = facts_of(user); fu += sum(v.lower() in pred.lower() for v in vals) / max(1, len(vals))
            hal += len(nums(pred) - nums(user) - nums(r['messages'][0]['content']))
            fh.write(json.dumps({'id': r['id'], 'metadata': r['metadata'], 'prediction': pred, 'raw': raw,
                                 'finish': s['done'], 'loop_trimmed': bool(loop), 'n_tokens': len(s['out']),
                                 'config': name}, ensure_ascii=False) + '\n')
    n = len(rows)
    summary[name] = dict(loop=n_loop / n, cap=n_cap / n, len_ratio=lr / n, facts_used=fu / n, unsupported_numbers=hal / n,
                         s_per_draft=secs, sampling=kwargs, chunk=chunk)
    print(f'{name:16s} {100 * n_loop / n:6.0f} {100 * n_cap / n:5.0f} {lr / n:8.2f} {fu / n:10.2f} {hal / n:12.2f} {secs:8.1f}')
json.dump(summary, open(f'{out_dir}/summary.json', 'w'), indent=1)
print(f'\nwritten: {out_dir}/<config>.jsonl and summary.json')
print('reading: loop% is what matters; len/gold near 1 and unsupported# near the greedy value mean the penalty did not')
print('wreck the text. greedy_loopstop has the greedy loop rate by construction; its s/draft is the latency saving.')
''')
code(r"""
# CELL 21 - DPO PAIRS (vLLM, about 35 min)
# DPO pairs: adapter SRC drafts N_GEN TRAIN prompts (never test rows); each draft that loops or hits the cap becomes the
# 'rejected' text and the gold sub-section the 'chosen' text. Same runtime as the decoding re-test (vLLM loaded;
# otherwise: stage 0, cell 4, then this cell). Resumable. About 35 minutes on an L4. Writes out/dpo_pairs.jsonl for
# SRC = 'A' and out/dpo_pairs_<SRC>.jsonl otherwise; every SRC drafts the same 400 prompts (SEED).
import os, sys, json, random, zlib
import torch

DRIVE = '/content/drive/MyDrive/sme_drhp'
SRC = 'A'                     # adapter that generates the rejected drafts (the one DPO will then train): 'A' or 'A_qa'
N_GEN, SEED = 400, 7
BASE = 'Qwen/Qwen2.5-7B-Instruct'
MAX_SEQ, CAP = 6144, 2200
PAIR_MAX = 4096               # prompt + longer completion, tokens: longer pairs are skipped (L4 memory in the DPO cell)
REJ_MAX = 1200                # rejected drafts are cut here: enough to carry the loop, bounded for memory

if '/content/sme' not in sys.path:
    sys.path.insert(0, '/content/sme')
import os
os.environ.setdefault('VLLM_ENGINE_READY_TIMEOUT_S', '3600')   # vLLM loads the 15 GB bf16 weights in a child process: no progress bar, 600 s default
try:
    from google.colab import userdata                            # optional HF_TOKEN secret: faster, un-throttled downloads
    os.environ.setdefault('HF_TOKEN', userdata.get('HF_TOKEN'))
except Exception:
    pass
from huggingface_hub import snapshot_download
snapshot_download(BASE, allow_patterns=['*.json', '*.safetensors', '*.txt'])   # visible download first; instant once cached
from vllm import LLM, SamplingParams
from vllm.inputs import TokensPrompt
from vllm.lora.request import LoRARequest
from transformers import AutoTokenizer
from data.prompts import trim_repeats

adapter = f'{DRIVE}/runs/{SRC}/adapter'
assert os.path.isfile(f'{adapter}/adapter_config.json'), f'no adapter at {adapter}'
tok = AutoTokenizer.from_pretrained(BASE)
if 'llm' not in globals():
    free, total = torch.cuda.mem_get_info()   # whole GPU (FAILURE_LOG 22)
    assert free > 0.8 * total, f'{(total - free) / 2**30:.1f} GB of the GPU is in use: Restart session, stage 0, cell 4, then this cell'
    llm = LLM(BASE, enable_lora=True, max_lora_rank=64, max_model_len=MAX_SEQ, gpu_memory_utilization=0.9)
lora = LoRARequest(f'src_{SRC}', 2 + zlib.crc32(SRC.encode()) % 10**6, adapter)   # one id per adapter: vLLM caches LoRAs by id

rows = [r for r in map(json.loads, open(f'{DRIVE}/out/train.jsonl', encoding='utf-8')) if r['metadata']['skill'] == 'drafting']
random.Random(SEED).shuffle(rows)
rows = rows[:N_GEN]
gen_path = f'{DRIVE}/work/dpo_gen_{SRC}.jsonl'
done = {}
if os.path.exists(gen_path):
    done = {g['id']: g for g in map(json.loads, open(gen_path, encoding='utf-8'))}
todo = [r for r in rows if r['id'] not in done]
print(f'{len(rows)} train drafting prompts | {len(done)} already drafted | {len(todo)} to draft')
with open(gen_path, 'a', encoding='utf-8') as fh:
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        prompts = [TokensPrompt(prompt_token_ids=tok(tok.apply_chat_template(r['messages'][:-1], tokenize=False,
                   add_generation_prompt=True), add_special_tokens=False).input_ids) for r in batch]
        outs = llm.generate(prompts, SamplingParams(temperature=0, max_tokens=CAP), lora_request=lora, use_tqdm=False)
        for r, o in zip(batch, outs):
            ids = list(o.outputs[0].token_ids)
            raw = tok.decode(ids, skip_special_tokens=True)
            pred, cut = trim_repeats(raw)
            g = {'id': r['id'], 'raw': raw, 'rejected': tok.decode(ids[:REJ_MAX], skip_special_tokens=True),
                 'finish': o.outputs[0].finish_reason, 'loop_trimmed': bool(cut), 'n_tokens': len(ids)}
            done[r['id']] = g
            fh.write(json.dumps(g, ensure_ascii=False) + '\n')
        fh.flush()
        print(f'  {min(i + 50, len(todo))}/{len(todo)} drafted')

pairs, n_bad, n_long = [], 0, 0
for r in rows:
    g = done[r['id']]
    if not (g['loop_trimmed'] or g['finish'] == 'length'):
        continue
    n_bad += 1
    prompt = r['messages'][:-1]
    chosen = r['messages'][-1]['content']
    n_prompt = len(tok(tok.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True), add_special_tokens=False).input_ids)
    n_comp = max(len(tok(chosen, add_special_tokens=False).input_ids), len(tok(g['rejected'], add_special_tokens=False).input_ids))
    if n_prompt + n_comp + 8 > PAIR_MAX:
        n_long += 1
        continue
    pairs.append({'id': r['id'], 'prompt': prompt,
                  'chosen': [{'role': 'assistant', 'content': chosen}],
                  'rejected': [{'role': 'assistant', 'content': g['rejected']}],
                  'meta': {'section_bucket': r['metadata']['section_bucket'], 'finish': g['finish'],
                           'loop_trimmed': g['loop_trimmed'], 'n_tokens': n_prompt + n_comp}})
out = f'{DRIVE}/out/dpo_pairs.jsonl' if SRC == 'A' else f'{DRIVE}/out/dpo_pairs_{SRC}.jsonl'
with open(out, 'w', encoding='utf-8') as fh:
    for p in pairs:
        fh.write(json.dumps(p, ensure_ascii=False) + '\n')
print(f'\n{len(rows)} drafts: {n_bad} looped or hit the cap ({100 * n_bad / len(rows):.0f}%), {n_long} of those too long for '
      f'{PAIR_MAX} tokens -> {len(pairs)} pairs written to {out}')
assert len(pairs) >= 60, 'too few pairs for DPO: raise N_GEN'
""")
code(r"""
# CELL 22 - DPO TRAINING (Unsloth, about 1 h)
# DPO on top of adapter SRC against looping. Policy = adapter SRC (trainable); reference = a second, frozen copy of it,
# so the loss moves the model away from its own looped drafts, not from the base model. Fresh runtime: stage 0, the
# Unsloth install (cell 13), Runtime > Restart session, stage 0, then this cell. About 1 hour on an L4 for 200 pairs.
# Writes runs/<SRC>_dpo. Then set RUN = '<SRC>_dpo' in the RUNS cell and run the held-out loss cell (16) and the
# predictions cell (17).
import os, sys, json, importlib.util
import torch

DRIVE = '/content/drive/MyDrive/sme_drhp'
SRC = 'A'                     # the SFT run to continue with DPO, as in the DPO pairs cell (21): 'A' or 'A_qa'
RUN = f'{SRC}_dpo'
BASE = 'Qwen/Qwen2.5-7B-Instruct'
MAX_SEQ = 6144
BETA, LR, EPOCHS, GA = 0.1, 1e-5, 2, 8
PAIR_MAX = 4096

assert importlib.util.find_spec('unsloth'), 'Unsloth not installed: run cell 13, Restart session, stage 0, then this cell'
free, total = torch.cuda.mem_get_info()   # whole GPU: vLLM's engine runs in another process, which memory_allocated misses
assert free > 0.8 * total, f'{(total - free) / 2**30:.1f} GB of the GPU is in use (a model from an earlier cell): Restart session, stage 0, then this cell'
from unsloth import FastLanguageModel
try:
    from unsloth import PatchDPOTrainer
    PatchDPOTrainer()
except ImportError:
    pass                                    # newer Unsloth patches DPOTrainer on import
from trl import DPOTrainer, DPOConfig
from datasets import Dataset

src = f'{DRIVE}/runs/{SRC}/adapter'
out_dir = f'{DRIVE}/runs/{RUN}'
os.makedirs(out_dir, exist_ok=True)
pairs_path = f'{DRIVE}/out/dpo_pairs.jsonl' if SRC == 'A' else f'{DRIVE}/out/dpo_pairs_{SRC}.jsonl'
assert os.path.isfile(pairs_path), f'{pairs_path} missing: run the DPO pairs cell (21) with SRC = {SRC!r} first'
pairs = [json.loads(l) for l in open(pairs_path, encoding='utf-8')]
pairs = [p for p in pairs if p['meta']['n_tokens'] <= PAIR_MAX]
print(f'{len(pairs)} pairs from {pairs_path}')

model, tok = FastLanguageModel.from_pretrained(src, max_seq_length=MAX_SEQ, load_in_4bit=True)
model.load_adapter(src, adapter_name='reference')            # frozen copy: the DPO reference
model.set_adapter('default')
for n, p in model.named_parameters():                        # train the 'default' LoRA only
    p.requires_grad_('lora_' in n and '.default.' in n)
n_train = sum(p.numel() for p in model.parameters() if p.requires_grad)
assert n_train > 0, 'no trainable LoRA parameters found'
print(f'trainable parameters: {n_train / 1e6:.1f}M (adapter {SRC})')
FastLanguageModel.for_training(model)

ds = Dataset.from_list([{'prompt': p['prompt'], 'chosen': p['chosen'], 'rejected': p['rejected']} for p in pairs])
fields = DPOConfig.__dataclass_fields__
want = dict(output_dir=f'{out_dir}/ckpt', beta=BETA, learning_rate=LR, num_train_epochs=EPOCHS,
            per_device_train_batch_size=1, gradient_accumulation_steps=GA, lr_scheduler_type='cosine', warmup_steps=3,
            logging_steps=2, bf16=True, optim='adamw_8bit', seed=3407, save_strategy='no', report_to='none',
            max_length=PAIR_MAX, max_prompt_length=PAIR_MAX - 256, max_completion_length=PAIR_MAX - 1024,
            truncation_mode='keep_start', model_adapter_name='default', ref_adapter_name='reference',
            remove_unused_columns=False, run_name=f'sme-drhp-{RUN}')
cfg_kw = {k: v for k, v in want.items() if k in fields}
missing = sorted(set(want) - set(cfg_kw))
if 'ref_adapter_name' not in cfg_kw:
    print('WARNING: this TRL has no ref_adapter_name: the reference will be the BASE model, not adapter A')
if missing:
    print('DPOConfig fields not in this TRL (skipped):', missing)
trainer = DPOTrainer(model=model, ref_model=None, args=DPOConfig(**cfg_kw), train_dataset=ds, processing_class=tok)
stats = trainer.train()
log = trainer.state.log_history
acc = [h['rewards/accuracies'] for h in log if 'rewards/accuracies' in h]
print(f'train loss {stats.training_loss:.3f} | reward accuracy last/first {acc[-1] if acc else float("nan"):.2f} / {acc[0] if acc else float("nan"):.2f}')
model.save_pretrained(f'{out_dir}/adapter', selected_adapters=['default'])
tok.save_pretrained(f'{out_dir}/adapter')
json.dump({'run': RUN, 'from': SRC, 'method': 'dpo', 'beta': BETA, 'lr': LR, 'epochs': EPOCHS, 'pairs': len(pairs),
           'base': BASE, 'log': log[-5:]}, open(f'{out_dir}/train_summary.json', 'w'), indent=1)
print(f'saved {out_dir}/adapter')
""")
code(r"""
# CELL 23 - LABEL-MASK CHECK (tokenizer only, 2 min)
# Label-mask check (2 minutes, tokenizer only, no model): shows exactly which tokens the SFT loss was trained on for one
# row, the way the training cell masks them. The trained span must be the assistant text and END WITH <|im_end|>;
# if <|im_end|> is masked out, the model never learned to stop and that alone explains the looping.
# Needs the Unsloth install (cell 13) and stage 0.
import sys, json, importlib.util
assert importlib.util.find_spec('unsloth'), 'Unsloth not installed on this machine: run cell 13, Restart session, stage 0, then this cell'
if '/content/sme' not in sys.path:
    sys.path.insert(0, '/content/sme')
from transformers import AutoTokenizer
from datasets import Dataset

DRIVE = '/content/drive/MyDrive/sme_drhp'
BASE = 'Qwen/Qwen2.5-7B-Instruct'
tok = AutoTokenizer.from_pretrained(BASE)
row = next(r for r in map(json.loads, open(f'{DRIVE}/out/train.jsonl', encoding='utf-8')) if r['metadata']['skill'] == 'drafting')
text = tok.apply_chat_template(row['messages'], tokenize=False)
ds = Dataset.from_list([{'text': text, 'input_ids': tok(text, add_special_tokens=False).input_ids}])
try:
    from unsloth_zoo.dataset_utils import train_on_responses_only

    class _T:                                   # the trainer attributes the masker reads
        pass
    t = _T(); t.train_dataset = ds; t.eval_dataset = None; t.processing_class = tok; t.tokenizer = tok
    t = train_on_responses_only(t, instruction_part='<|im_start|>user\n', response_part='<|im_start|>assistant\n')
    ex = t.train_dataset[0]
    ids, labels = ex['input_ids'], ex['labels']
    kept = [i for i, l in enumerate(labels) if l != -100]
    span = tok.decode([ids[i] for i in kept])
    print(f'{len(ids)} tokens, {len(kept)} in the loss ({100 * len(kept) / len(ids):.0f}%)')
    print('trained span starts:', repr(span[:120]))
    print('trained span ends:  ', repr(span[-80:]))
    ends_ok = tok.convert_tokens_to_ids('<|im_end|>') in [ids[i] for i in kept[-3:]]
    print('\nVERDICT:', 'OK: <|im_end|> is trained, the model was taught to stop' if ends_ok else
          'PROBLEM: <|im_end|> is NOT in the loss: fix the mask before any further SFT')
except Exception as e:
    print(f'inconclusive: the masker could not run outside a trainer ({type(e).__name__}: {e})')
    print('fallback: the template puts the assistant text between these markers; check that the training cell keeps the end:')
    i = text.rfind('<|im_start|>assistant\n')
    print(repr(text[i:i + 80]), '...', repr(text[-40:]))
""")

md("""
## Stage 2c: Q&A pairs for the third skill (A100, 220 calls, about 20-30 minutes; added 14 Nov 2026)

Placed last so the cell numbers above stay as they were. The teacher writes 2 question-answer pairs per passage for
question answering with Responsible-AI guardrails (`trainset/work/qa_jobs.jsonl`, made on the laptop with
`python -m data.qa jobs`: 180 train-split and 40 test-split passages). A100 runtime: stage 0 (cell 3), the vLLM
install (cell 4), then cell 25. Resumable like stage 2. Then, on the laptop:
`python -m data.qa rows --responses trainset/work/qa_responses.jsonl` builds `out/train_v2.jsonl` and
`out/test_v2.jsonl`; upload both to Drive `out/` and train run `A_qa` (cells 14-17), then DPO with `SRC = 'A_qa'`
(cells 21-22) and cells 16-17 with `RUN = 'A_qa_dpo'`.
""")
code("# CELL 25 - Q&A PAIRS (teacher, A100)\n" + TEACHER_CELL.format(jobs="qa_jobs.jsonl", out="qa_responses.jsonl"))

nb = {"cells": cells, "metadata": {"accelerator": "GPU", "colab": {"provenance": []},
                                   "kernelspec": {"display_name": "Python 3", "name": "python3"}},
      "nbformat": 4, "nbformat_minor": 0}


def package(path):
    keep_dirs = ("data", "teacher", "mock", "draft", "extract", "rag", "serve")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for d in keep_dirs:
            for base, _dirs, files in os.walk(os.path.join(ROOT, d)):
                if "__pycache__" in base:
                    continue
                for f in files:
                    if f.endswith(".py"):
                        full = os.path.join(base, f)
                        z.write(full, os.path.relpath(full, ROOT).replace(os.sep, "/"))   # forward slashes (FAILURE_LOG 28)
        for rel in ("trainset/screen/screen_jobs.jsonl", "trainset/screen/screen_units.jsonl", "trainset/work/teacher_jobs.jsonl",
                    "trainset/work/gapfill_jobs.jsonl", "trainset/work/qa_jobs.jsonl", "trainset/work/common_words.json",
                    "trainset/screen/reviewer_labels.json"):
            full = os.path.join(ROOT, rel)
            if os.path.isfile(full):
                z.write(full, rel)
    return path


if __name__ == "__main__":
    nb_path = os.path.join(HERE, "sme_drhp_colab.ipynb")
    with open(nb_path, "w", encoding="utf-8") as fh:
        json.dump(nb, fh, indent=1, ensure_ascii=False)
    z = package(os.path.join(HERE, "sme_drhp_colab.zip"))
    print(f"{nb_path} ({len(cells)} cells)\n{z} ({os.path.getsize(z) // 1024} KB)")
