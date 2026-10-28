#!/usr/bin/env bash
# Measure DSpark on this host: exactness (greedy must be identical) + decode speed.
set -u
LL=~/bin/llamacpp/llama-b11936
MODEL=~/models/minicpm5/MiniCPM5-2B-Q8_0.gguf
DRAFT=~/models/minicpm5/MiniCPM5-2B-DSpark.gguf
OUT=/tmp/dspark_bench.txt
: > "$OUT"

PROMPTS=(
"Explain why a low-carbohydrate diet can be harmful for a patient with reactive hypoglycaemia documented on CGM."
"List the herb-drug interactions a practitioner must screen for before recommending St John's Wort, with mechanisms."
"A patient has TSH 5.8 mIU/L, free T4 12 pmol/L and TPO antibodies 220 IU/mL. What does this mean and what would you check next?"
"Why does grapefruit juice raise the concentration of some statins?"
"Describe how ferritin behaves as an acute-phase reactant and what that means for interpreting iron studies."
)

run () {  # $1 = label, $2 = port, $3.. extra flags
  local label="$1" port="$2"; shift 2
  echo "== $label (port $port)" | tee -a "$OUT"
  "$LL/llama-server" -m "$MODEL" "$@" -c 2048 -np 1 -t 6 --jinja \
      --no-reasoning-preserve --host 127.0.0.1 --port "$port" >/tmp/bench_srv_$port.log 2>&1 &
  local pid=$!
  for i in $(seq 1 90); do curl -sf -o /dev/null "http://127.0.0.1:$port/health" && break; sleep 1; done

  local total_ms=0 total_tok=0
  for idx in "${!PROMPTS[@]}"; do
    local payload
    payload=$(python3 - "$port" "${PROMPTS[$idx]}" <<'PY'
import json,sys
port, prompt = sys.argv[1], sys.argv[2]
print(json.dumps({"model":"m","messages":[{"role":"user","content":prompt}],
 "temperature":0,"top_k":1,"max_tokens":220,"seed":42,
 "chat_template_kwargs":{"enable_thinking":False}}))
PY
)
    curl -s "http://127.0.0.1:$port/v1/chat/completions" -H 'Content-Type: application/json' \
         -d "$payload" -o "/tmp/resp_${port}_${idx}.json"
    local ptok ctok pms ems
    read ptok ctok pms ems < <(python3 - "/tmp/resp_${port}_${idx}.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
t=d.get("timings",{})
print(d["usage"]["prompt_tokens"], d["usage"]["completion_tokens"],
      int(t.get("prompt_ms",0)), int(t.get("predicted_ms",0)))
PY
)
    local tps
    tps=$(python3 -c "print(f'{$ctok/($ems/1000):.2f}' if $ems else 'na')")
    echo "   p$idx prompt=${ptok}t gen=${ctok}t decode=${tps} tok/s" | tee -a "$OUT"
    total_ms=$((total_ms+ems)); total_tok=$((total_tok+ctok))
  done
  python3 -c "print(f'   AGGREGATE decode: {$total_tok/($total_ms/1000):.2f} tok/s over $total_tok tokens')" | tee -a "$OUT"
  kill $pid 2>/dev/null; wait $pid 2>/dev/null; sleep 3
}

run "baseline (no speculation)" 8100
run "DSpark (draft block 7)" 8101 -md "$DRAFT" --spec-type draft-dspark --spec-draft-n-max 7

echo "== exactness check ==" | tee -a "$OUT"
for idx in "${!PROMPTS[@]}"; do
  if cmp -s "/tmp/resp_8100_${idx}.json" "/tmp/resp_8101_${idx}.json" 2>/dev/null; then
    echo "   p$idx: byte-identical response file" | tee -a "$OUT"
  else
    python3 - "/tmp/resp_8100_${idx}.json" "/tmp/resp_8101_${idx}.json" <<'PY' | tee -a "$OUT"
import json,sys
a=json.load(open(sys.argv[1]))["choices"][0]["message"]["content"]
b=json.load(open(sys.argv[2]))["choices"][0]["message"]["content"]
print(f"   p{idx}: {'IDENTICAL text' if a==b else 'DIFFERS'} ({len(a)} vs {len(b)} chars)")
PY
  fi
done
echo "== done ==" | tee -a "$OUT"
