# FoxMQ Warmup - Stateful Handshake

Completed warmup for Vertex Swarm Challenge 2026.

## Features
- Two agents (agent_a, agent_b) with P2P handshake
- Heartbeat every 5 seconds
- Role change propagation (<1 sec)
- Stale detection (10 sec timeout)
- Auto-recovery

## Run
```bash
pip install -r requirements.txt
python node.py --host 127.0.0.1 --port 1883 --username agent_a --password agent_a --agent-id agent_a
```

## Demo
[Add video link]
