#!/usr/bin/env bash
# Footprint probe: how small can materia's engine actually run?
set -u
LL=~/bin/llamacpp/llama-b11936
OUT=/tmp/footprint.txt
: > "$OUT"

probe () {
  local model="$1" ctx="$2" np="$3" thr="$4" label="$5"
  echo "== $label : $(basename $model) -c $ctx -np $np -t $thr" | tee -a "$OUT"
  "$LL/llama-server" -m "$model" -c "$ctx" -np "$np" -t "$thr" --jinja \
      --no-reasoning-preserve --port 8101 >/tmp/probe_server.log 2>&1 &
  local pid=$!
  for i in $(seq 1 60); do
    curl -sf -o /dev/null http://127.0.0.1:8101/health && break
    sleep 1
  done
  local rss idle
  rss=$(ps -o rss= -p $pid | tr -d ' ')
  idle=$((rss/1024))
  echo "   RSS after load : ${idle} MB" | tee -a "$OUT"
  # one real request
  local t0=$(date +%s%N)
  curl -s http://127.0.0.1:8101/v1/chat/completions -H 'Content-Type: application/json' \
    -d '{"model":"m","messages":[{"role":"user","content":"Answer with ONLY the letter.\n\nWhich vitamin deficiency causes megaloblastic anaemia with neurological signs?\nA) Vitamin C\nB) Vitamin B12\nC) Vitamin D\nD) Vitamin K\n\nAnswer:"}],"temperature":0,"max_tokens":64,"chat_template_kwargs":{"enable_thinking":false}}' \
    -o /tmp/probe_resp.json
  local t1=$(date +%s%N)
  local ms=$(( (t1-t0)/1000000 ))
  local ans=$(python3 -c "import json;print(json.load(open('/tmp/probe_resp.json'))['choices'][0]['message']['content'])" 2>/dev/null)
  rss=$(ps -o rss= -p $pid | tr -d ' ')
  echo "   RSS in use     : $((rss/1024)) MB" | tee -a "$OUT"
  echo "   answer='$ans'  latency=${ms}ms" | tee -a "$OUT"
  kill $pid 2>/dev/null; wait $pid 2>/dev/null
  sleep 3
}

probe ~/models/minicpm5/MiniCPM5-2B-Q4_K_M.gguf 1024 1 4 "tier-1 phone/mini-pc"
probe ~/models/minicpm5/MiniCPM5-2B-Q4_K_M.gguf 2048 1 4 "tier-2 single-user"
probe ~/models/minicpm5/MiniCPM5-2B-Q8_0.gguf   2048 1 4 "tier-3 single-user Q8"
probe ~/models/minicpm5/MiniCPM5-2B-Q8_0.gguf   4096 2 6 "tier-4 this host (reference)"
echo "== done ==" | tee -a "$OUT"
