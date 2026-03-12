# warmup-foxmq-python

Starter template for the **Tashi Vertex Swarm Challenge 2026 — The Stateful Handshake** warm-up, using **FoxMQ** and Python.

FoxMQ is a Byzantine fault-tolerant MQTT 5.0 broker powered by Vertex consensus. Any standard MQTT client library works against it — messages are consensus-ordered by Vertex before delivery, so every subscriber sees the exact same event sequence.

---

## Pre-requisites

- Python 3.8+
- A running FoxMQ broker (see setup below)

---

## Step 1 — Start FoxMQ

### Option A: Binary (fastest for local dev)

**Linux (amd64)**
```sh
curl -LO https://github.com/tashigit/foxmq/releases/download/v0.3.0/foxmq_0.3.0_linux-amd64.zip
unzip foxmq_0.3.0_linux-amd64.zip
chmod +x foxmq
```

**macOS (Apple Silicon + Intel universal)**
```sh
curl -LO https://github.com/tashigit/foxmq/releases/download/v0.3.0/foxmq_0.3.0_macos-universal.zip
unzip foxmq_0.3.0_macos-universal.zip
chmod +x foxmq
```

**Windows (PowerShell)**
```powershell
curl -LO https://github.com/tashigit/foxmq/releases/download/v0.3.0/foxmq_0.3.0_windows-amd64.zip
Expand-Archive foxmq_0.3.0_windows-amd64.zip .
```

**Then set up and run:**
```sh
# Generate address book (1 node for local testing)
./foxmq address-book from-range 127.0.0.1 19793 19793

# Create a user for each agent
./foxmq user add agent_a
./foxmq user add agent_b

# Start the broker
./foxmq run --secret-key-file=foxmq.d/key_0.pem
```

### Option B: Docker

```sh
docker network create foxmq_net

docker run --rm \
  -v ./foxmq.d/:/foxmq.d/ \
  ghcr.io/tashigit/foxmq:latest \
  address-book from-list 172.18.0.2:19793

docker run --rm \
  -v ./foxmq.d/:/foxmq.d/ \
  ghcr.io/tashigit/foxmq:latest \
  user add agent_a

docker run -d --name foxmq-0 \
  --network foxmq_net \
  -p 1883:1883 \
  -v ./foxmq.d/:/foxmq.d/ \
  ghcr.io/tashigit/foxmq:latest \
  run --secret-key-file=/foxmq.d/key_0.pem
```

> For high availability in production, use **4+ nodes** (formula: `3N + 1` where N = failures tolerated).

---

## Step 2 — Install Python dependencies

```sh
pip install -r requirements.txt
```

---

## Step 3 — Run two agents

```sh
# Terminal 1 – Agent A
python node.py --host 127.0.0.1 --port 1883 \
               --username agent_a --password <PASSWORD_A> \
               --agent-id agent_a

# Terminal 2 – Agent B
python node.py --host 127.0.0.1 --port 1883 \
               --username agent_b --password <PASSWORD_B> \
               --agent-id agent_b
```

You should see both agents printing `[RECV]` lines as messages come through FoxMQ's BFT consensus layer.

---

## Your Challenge

Extend `node.py` to complete the warm-up:

- [ ] **Handshake** — publish a `HELLO` JSON payload to `swarm/hello` on connect
- [ ] **Heartbeats** — publish a `HEARTBEAT` payload to `swarm/state` on a timer
- [ ] **Replicated state** — maintain `{ peer_id, last_seen_ms, role, status }` updated from incoming messages
- [ ] **Trigger action** — have Agent A change its `role`; Agent B must mirror it in <1 second
- [ ] **Stale detection** — mark a peer as `"stale"` if its `last_seen_ms` is >10 s old
- [ ] **Recovery** — show the agent reconnecting and state resuming automatically

Look for `# TODO` comments in `node.py` to know where to add your logic.

---

## How FoxMQ ordering works

```
Agent A publishes → local FoxMQ node → Vertex consensus → all FoxMQ nodes → Agent B
                                            ↑
                          fair ordering happens here (BFT, sub-100ms)
```

Because ordering is handled by Vertex, your `on_message` handler will fire **in the same order** on every connected agent — no extra coordination needed.

---

## Submitting

Record a short terminal session (30–60 s) showing:
1. Discovery + handshake
2. Active heartbeats
3. State replication (role change mirrored)
4. A killed-then-recovered agent

Drop it in Discord `#shipping-log` to claim your **Stateful Handshake** badge!

---

*Docs: [FoxMQ](https://docs.tashi.network/resources/foxmq)*
