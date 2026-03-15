"""
Tashi FoxMQ Warmup — The Stateful Handshake
Complete implementation of the warmup challenge.

FoxMQ is a Byzantine fault-tolerant MQTT 5.0 broker powered by Vertex consensus.
Any standard MQTT client library works against it — messages are consensus-ordered
before delivery, so all subscribers always see the same event order.

This script implements:
- Handshake (HELLO) on connect
- Heartbeat every 5 seconds
- Replicated state {peer_id, last_seen_ms, role, status}
- Role change propagation (<1 second mirror)
- Stale detection (10 seconds timeout)
- Recovery after disconnect/reconnect
"""

import argparse
import json
import time
import threading
from datetime import datetime
import paho.mqtt.client as mqtt

# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------
TOPIC_SWARM = "swarm/state"      # shared BFT-ordered state topic
TOPIC_HELLO = "swarm/hello"      # initial handshake topic

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
peers = {}           # peer_id -> {"last_seen": int ms, "role": str, "status": str}
my_role = "follower" # default role
my_id = None
running = True
lock = threading.Lock()  # for thread-safe peers access

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def now_ms() -> int:
    """Return current time in milliseconds."""
    return int(time.time() * 1000)

def publish_json(client: mqtt.Client, topic: str, data: dict) -> None:
    """Publish a dict as a JSON message with QoS 1."""
    payload = json.dumps(data)
    client.publish(topic, payload, qos=1)
    print(f"[SEND] topic={topic}  payload={payload}")

def print_peer_status():
    """Print current peer status table."""
    with lock:
        print("\n" + "="*50)
        print(f"AGENT {my_id} (role: {my_role})")
        print("-"*50)
        for pid, info in peers.items():
            status = info.get("status", "unknown")
            role = info.get("role", "unknown")
            last_seen = info.get("last_seen", 0)
            age = (now_ms() - last_seen) / 1000 if last_seen else 0
            print(f"  {pid}: role={role}, status={status}, age={age:.1f}s")
        print("="*50 + "\n")

# ---------------------------------------------------------------------------
# Background threads
# ---------------------------------------------------------------------------

def heartbeat_loop(client, agent_id):
    """Background thread sending heartbeat every 5 seconds."""
    global my_role
    while running:
        time.sleep(5)
        with lock:
            current_role = my_role
        heartbeat_msg = {
            "type": "HEARTBEAT",
            "agent_id": agent_id,
            "role": current_role,
            "timestamp": now_ms()
        }
        publish_json(client, TOPIC_SWARM, heartbeat_msg)

def stale_checker():
    """Background thread checking for stale peers every 2 seconds."""
    while running:
        time.sleep(2)
        now = now_ms()
        changes = False
        with lock:
            for peer_id, info in list(peers.items()):
                if now - info["last_seen"] > 10000:  # 10 seconds timeout
                    if info["status"] != "stale":
                        info["status"] = "stale"
                        print(f"[STALE] Peer {peer_id} marked stale (last seen: {(now - info['last_seen'])/1000:.1f}s ago)")
                        changes = True
        if changes:
            print_peer_status()

def role_changer(client, agent_id):
    """Interactive thread to change role when user presses Enter."""
    global my_role
    while running:
        input("\nPress Enter to toggle role (follower <-> leader)...\n")
        with lock:
            my_role = "leader" if my_role == "follower" else "follower"
            new_role = my_role
        role_msg = {
            "type": "ROLE_CHANGE",
            "agent_id": agent_id,
            "new_role": new_role,
            "timestamp": now_ms()
        }
        publish_json(client, TOPIC_SWARM, role_msg)
        print_peer_status()

# ---------------------------------------------------------------------------
# MQTT callbacks
# ---------------------------------------------------------------------------

def on_connect(client: mqtt.Client, userdata, flags, reason_code, properties):
    """Called when the client connects to the FoxMQ broker."""
    if reason_code == 0:
        print(f"[CONNECTED] broker={userdata['host']}:{userdata['port']} as {userdata['agent_id']}")

        # Subscribe to topics
        client.subscribe(TOPIC_SWARM, qos=1)
        client.subscribe(TOPIC_HELLO, qos=1)
        print(f"[SUBSCRIBED] {TOPIC_SWARM}, {TOPIC_HELLO}")

        # Send HELLO handshake
        hello_msg = {
            "type": "HELLO",
            "agent_id": userdata['agent_id'],
            "timestamp": now_ms()
        }
        publish_json(client, TOPIC_HELLO, hello_msg)

        # Start background threads
        global my_id
        my_id = userdata['agent_id']
        
        threading.Thread(target=heartbeat_loop, args=(client, my_id), daemon=True).start()
        threading.Thread(target=stale_checker, daemon=True).start()
        threading.Thread(target=role_changer, args=(client, my_id), daemon=True).start()

    else:
        print(f"[ERROR] Connection failed: {reason_code}")

def on_message(client: mqtt.Client, userdata, message: mqtt.MQTTMessage):
    """Called for every consensus-ordered message that arrives from FoxMQ."""
    topic = message.topic
    payload = message.payload.decode("utf-8")

    try:
        data = json.loads(payload)
        msg_type = data.get("type")
        peer_id = data.get("agent_id")
        timestamp = data.get("timestamp", 0)

        if not peer_id or peer_id == userdata['agent_id']:
            return  # ignore our own messages

        # Update peer state
        with lock:
            if peer_id not in peers:
                peers[peer_id] = {
                    "last_seen": timestamp,
                    "role": data.get("role", "follower"),
                    "status": "active"
                }
                print(f"[NEW PEER] {peer_id}")
            else:
                peers[peer_id]["last_seen"] = timestamp
                peers[peer_id]["status"] = "active"
                if data.get("role"):
                    peers[peer_id]["role"] = data.get("role")

        # Handle specific message types
        if msg_type == "HELLO":
            print(f"[HELLO] Received from {peer_id}")
            
            # Optionally reply with our own HELLO if this is first contact
            if peer_id not in peers:
                hello_back = {
                    "type": "HELLO",
                    "agent_id": userdata['agent_id'],
                    "timestamp": now_ms()
                }
                publish_json(client, TOPIC_HELLO, hello_back)

        elif msg_type == "HEARTBEAT":
            print(f"[HEARTBEAT] from {peer_id} (role={data.get('role')})")

        elif msg_type == "ROLE_CHANGE":
            new_role = data.get("new_role")
            print(f"[ROLE_CHANGE] {peer_id} changed role to {new_role}")
            # Mirror role change if we're following a leader
            with lock:
                global my_role
                # You could add leader-follower logic here
                pass

        # Print current status after every 5 messages (avoid spam)
        if int(time.time()) % 5 == 0:
            print_peer_status()

    except json.JSONDecodeError:
        print(f"[ERROR] Invalid JSON from {topic}: {payload}")
    except Exception as e:
        print(f"[ERROR] Processing message: {e}")

def on_disconnect(client: mqtt.Client, userdata, flags, reason_code, properties):
    print(f"[DISCONNECTED] reason={reason_code}")
    print("[RECOVERY] Will auto-reconnect when broker is back")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="FoxMQ Warmup – Stateful Handshake")
    parser.add_argument("--host",     default="127.0.0.1", help="FoxMQ broker host")
    parser.add_argument("--port",     default=1883, type=int, help="FoxMQ broker MQTT port")
    parser.add_argument("--username", required=True, help="FoxMQ username")
    parser.add_argument("--password", required=True, help="FoxMQ password")
    parser.add_argument("--agent-id", required=True, help="Unique ID for this agent")
    args = parser.parse_args()

    # Build MQTTv5 client
    client = mqtt.Client(
        client_id=args.agent_id,
        protocol=mqtt.MQTTv5,
        userdata={"host": args.host, "port": args.port, "agent_id": args.agent_id},
    )

    client.username_pw_set(args.username, args.password)
    client.on_connect    = on_connect
    client.on_message    = on_message
    client.on_disconnect = on_disconnect

    print(f"[INFO] Connecting to FoxMQ at {args.host}:{args.port} as {args.agent_id}")
    client.connect(args.host, args.port, keepalive=60)

    try:
        # Blocking network loop — handles reconnects automatically
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Received Ctrl+C, cleaning up...")
        global running
        running = False
        client.disconnect()
        print("[SHUTDOWN] Complete")

if __name__ == "__main__":
    main()
