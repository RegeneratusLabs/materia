# Deploying materia over Tailscale

This runs materia as a persistent systemd **user** service, bound to localhost, and exposes it
only inside the tailnet through `tailscale serve`. No GPU, no public port, no cloud.

## Install

```bash
mkdir -p ~/.config/systemd/user
cp deploy/materia.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now materia.service
```

The service starts the web app and the CPU OCR engine on `127.0.0.1:8890`. The sample report and
Plan work without OCR; OCR is there for uploads.

## Expose to the tailnet

```bash
tailscale serve --bg --https=8451 http://127.0.0.1:8890
```

Then open:

```
https://homelab.taildace6c.ts.net:8451/
```

The URL is **tailnet only**. Use `tailscale serve status` to inspect it and
`tailscale serve --https=8451 off` to remove it.

## Operate

```bash
systemctl --user status materia.service
journalctl --user -u materia.service -f
systemctl --user restart materia.service
systemctl --user stop materia.service
```

Logs are also appended to `logs/materia-service.log`.

## CPU chat

The service starts with deterministic chat. To use the Q4 CPU model, start `llama-server` on
port 8099 and set `MATERIA_CHAT_BASE_URL` / `MATERIA_CHAT_MODEL` in the unit. Do not run the OCR
and chat models concurrently on a small host; `materia.llm.load_phase()` enforces the switch.
