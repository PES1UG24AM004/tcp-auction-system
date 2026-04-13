import socket, ssl, threading, json, time, uuid, os, sys

HOST      = "0.0.0.0"
PORT      = 9999
CERT_FILE = "server.crt"
KEY_FILE  = "server.key"

SNIPE_WINDOW    = 10
SNIPE_EXTENSION = 15

auctions      = {}
auctions_lock = threading.Lock()
clients       = {}
clients_lock  = threading.Lock()
server_running = True


#make_certificate
def make_certificate():
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        return
    print("[Server] Generating TLS certificate...")
    try:
        import subprocess
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048",
             "-keyout", KEY_FILE, "-out", CERT_FILE,
             "-days", "3650", "-nodes",
             "-subj", "/CN=AuctionServer/O=AuctionApp/C=US"],
            check=True, capture_output=True)
        print("[Server] Certificate ready.")
    except Exception as e:
        print(f"[Server] openssl failed: {e}  -- run generate_cert.py manually.")
        sys.exit(1)


# send
def send(conn, d):
    try:
        conn.sendall((json.dumps(d) + "\n").encode())
    except Exception:
        pass


# broadcast
def broadcast(d, skip_id=None):
    with clients_lock:
        for bid_id, info in list(clients.items()):
            if bid_id != skip_id:
                send(info["conn"], d)


# time_remaining
def time_remaining(a):
    if a["state"] != "active" or a["start_time"] is None:
        return 0
    return max(0.0, a["duration"] - (time.time() - a["start_time"]))


# reset_timer
def reset_timer(auction_id, a):
    if a.get("timer"):
        a["timer"].cancel()
    t = threading.Timer(time_remaining(a), end_auction, args=[auction_id])
    t.daemon = True
    t.start()
    a["timer"] = t


# end_auction
def end_auction(auction_id):
    with auctions_lock:
        a = auctions.get(auction_id)
        if not a or a["state"] != "active":
            return
        a["state"] = "ended"
    winner = a["current_bidder"]
    price  = a["current_bid"] or 0
    print(f"[Server] Auction {auction_id} ended -- winner: {winner}, price: ${price:.2f}")
    broadcast({
        "type":        "auction_ended",
        "auction_id":  auction_id,
        "item":        a["item"],
        "winner":      winner,
        "final_price": price,
        "total_bids":  len(a["bid_history"]),
    })


# handle_command
def handle_command(conn, bidder_id, raw):
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        send(conn, {"type": "error", "message": "Invalid JSON"}); return
    if not isinstance(msg, dict):
        send(conn, {"type": "error", "message": "Expected JSON object"}); return

    cmd = msg.get("command", "")

    if cmd == "list":
        with auctions_lock:
            result = [{
                "id":             aid,
                "item":           a["item"],
                "state":          a["state"],
                "current_bid":    a["current_bid"] if a["current_bid"] is not None else a["starting_price"],
                "bid_count":      len(a["bid_history"]),
                "time_remaining": round(time_remaining(a), 1),
                "creator_id":     a["creator_id"],
            } for aid, a in auctions.items()]
        send(conn, {"type": "auction_list", "auctions": result})

    elif cmd == "create":
        item = msg.get("item", "")
        if not isinstance(item, str) or not item.strip() or len(item) > 50:
            send(conn, {"type": "error", "message": "Item name must be 1-50 chars"}); return
        try:
            price = float(msg["starting_price"])
            dur   = int(msg["duration"])
            inc   = float(msg.get("min_increment", 1.0))
        except (KeyError, TypeError, ValueError):
            send(conn, {"type": "error", "message": "Invalid number in create"}); return
        if not (0 < price <= 1_000_000):
            send(conn, {"type": "error", "message": "Price must be $0.01-$1,000,000"}); return
        if not (10 <= dur <= 3600):
            send(conn, {"type": "error", "message": "Duration must be 10-3600 seconds"}); return
        if inc < 0.01:
            send(conn, {"type": "error", "message": "Min increment must be >= $0.01"}); return
        aid = str(uuid.uuid4())[:8]
        with auctions_lock:
            if len(auctions) >= 100:
                send(conn, {"type": "error", "message": "Server full (100 auction limit)"}); return
            auctions[aid] = {
                "item":           item.strip(),
                "starting_price": price,
                "duration":       dur,
                "min_increment":  inc,
                "state":          "pending",
                "current_bid":    None,
                "current_bidder": None,
                "bid_history":    [],
                "start_time":     None,
                "timer":          None,
                "participants":   set(),
                "creator_id":     bidder_id,
            }
        send(conn, {"type": "auction_created", "auction_id": aid})
        broadcast({"type": "new_auction", "auction_id": aid,
                   "item": item.strip(), "starting_price": price,
                   "duration": dur, "creator_id": bidder_id}, skip_id=bidder_id)
        print(f"[Server] Auction {aid} created: '{item}' by {bidder_id}")

    elif cmd == "start":
        aid = msg.get("auction_id", "")
        with auctions_lock:
            a = auctions.get(aid)
            if not a:
                send(conn, {"type": "error", "message": "Auction not found"}); return
            if a["creator_id"] != bidder_id:
                send(conn, {"type": "error", "message": "Only the creator can start this auction"}); return
            if a["state"] != "pending":
                send(conn, {"type": "error", "message": "Auction already started"}); return
            a["state"]      = "active"
            a["start_time"] = time.time()
            reset_timer(aid, a)
        broadcast({"type": "auction_started", "auction_id": aid,
                   "item": a["item"], "duration": a["duration"]})
        print(f"[Server] Auction {aid} started by {bidder_id}")

    elif cmd == "bid":
        aid = msg.get("auction_id", "")
        try:
            amount = float(msg.get("amount", 0))
        except (TypeError, ValueError):
            send(conn, {"type": "error", "message": "Bid amount must be a number"}); return
        if amount <= 0:
            send(conn, {"type": "error", "message": "Bid must be positive"}); return
        with auctions_lock:
            a = auctions.get(aid)
            if not a or a["state"] != "active":
                send(conn, {"type": "bid_response", "success": False,
                            "message": "Auction not active"}); return
            if a["creator_id"] == bidder_id:
                send(conn, {"type": "bid_response", "success": False,
                            "message": "You cannot bid on your own auction"}); return
            min_bid = (a["current_bid"] + a["min_increment"]) if a["current_bid"] is not None else a["starting_price"]
            if amount < min_bid:
                send(conn, {"type": "bid_response", "success": False,
                            "message": f"Bid must be at least ${min_bid:.2f}"}); return
            a["current_bid"]    = amount
            a["current_bidder"] = bidder_id
            a["bid_history"].append({"bidder": bidder_id, "amount": amount, "time": time.time()})
            a["participants"].add(bidder_id)
            sniped = False
            if 0 < time_remaining(a) <= SNIPE_WINDOW:
                a["duration"] += SNIPE_EXTENSION
                reset_timer(aid, a)
                sniped = True
                print(f"[Server] Anti-snipe on {aid} -- extended {SNIPE_EXTENSION}s")
            t_left = round(time_remaining(a), 1)
        snipe_note = f" (extended +{SNIPE_EXTENSION}s)" if sniped else ""
        send(conn, {"type": "bid_response", "success": True,
                    "message": f"Bid ${amount:.2f} accepted!{snipe_note}"})
        broadcast({"type": "new_high_bid", "auction_id": aid,
                   "amount": amount, "bidder_id": bidder_id,
                   "time_remaining": t_left}, skip_id=bidder_id)
        print(f"[Server] Bid ${amount:.2f} on {aid} by {bidder_id}")

    elif cmd == "end_now":
        aid = msg.get("auction_id", "")
        with auctions_lock:
            a = auctions.get(aid)
            if not a:
                send(conn, {"type": "error", "message": "Auction not found"}); return
            if a["creator_id"] != bidder_id:
                send(conn, {"type": "error", "message": "Only the creator can end this auction"}); return
            if a["state"] != "active":
                send(conn, {"type": "error", "message": "Auction is not active"}); return
            if a.get("timer"):
                a["timer"].cancel()
                a["timer"] = None
        end_auction(aid)
        print(f"[Server] Auction {aid} force-ended by creator {bidder_id}")

    elif cmd == "add_time":
        aid     = msg.get("auction_id", "")
        seconds = msg.get("seconds", 0)
        try:
            seconds = int(seconds)
        except (TypeError, ValueError):
            send(conn, {"type": "error", "message": "seconds must be an integer"}); return
        if seconds <= 0 or seconds > 3600:
            send(conn, {"type": "error", "message": "seconds must be 1-3600"}); return
        with auctions_lock:
            a = auctions.get(aid)
            if not a:
                send(conn, {"type": "error", "message": "Auction not found"}); return
            if a["creator_id"] != bidder_id:
                send(conn, {"type": "error", "message": "Only the creator can add time"}); return
            if a["state"] != "active":
                send(conn, {"type": "error", "message": "Auction is not active"}); return
            a["duration"] += seconds
            reset_timer(aid, a)
            new_remaining = round(time_remaining(a), 1)
        broadcast({"type": "time_added", "auction_id": aid,
                   "added": seconds, "time_remaining": new_remaining})
        print(f"[Server] +{seconds}s added to {aid} by creator {bidder_id}")

    elif cmd == "status":
        aid = msg.get("auction_id", "")
        with auctions_lock:
            a = auctions.get(aid)
            if not a:
                send(conn, {"type": "error", "message": "Auction not found"}); return
            send(conn, {
                "type":           "auction_status",
                "auction_id":     aid,
                "item":           a["item"],
                "state":          a["state"],
                "current_bid":    a["current_bid"] if a["current_bid"] is not None else a["starting_price"],
                "leader":         a["current_bidder"],
                "time_remaining": round(time_remaining(a), 1),
                "bid_count":      len(a["bid_history"]),
                "creator_id":     a["creator_id"],
            })
    else:
        send(conn, {"type": "error", "message": f"Unknown command: {cmd}"})


# handle_client
def handle_client(conn, addr, bidder_id):
    print(f"[Server] Connected: {bidder_id} from {addr}")
    send(conn, {"type": "welcome", "bidder_id": bidder_id})
    buf = ""
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            buf += data.decode("utf-8", errors="replace")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if line:
                    handle_command(conn, bidder_id, line)
    except ConnectionResetError:
        pass
    except Exception as e:
        print(f"[Server] Error ({bidder_id}): {e}")
    finally:
        with clients_lock:
            clients.pop(bidder_id, None)
        try:
            conn.close()
        except Exception:
            pass
        print(f"[Server] Disconnected: {bidder_id}")


# main
def main():
    make_certificate()
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(50)
    srv.settimeout(1.0)
    print(f"[Server] Listening on port {PORT} (TLS)")
    try:
        while server_running:
            try:
                raw_conn, addr = srv.accept()
            except socket.timeout:
                continue
            try:
                conn = ssl_ctx.wrap_socket(raw_conn, server_side=True)
            except Exception as e:
                print(f"[Server] TLS handshake failed {addr}: {e}")
                raw_conn.close()
                continue
            bidder_id = str(uuid.uuid4())[:8]
            with clients_lock:
                clients[bidder_id] = {"conn": conn, "addr": addr}
            threading.Thread(target=handle_client, args=(conn, addr, bidder_id), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
    finally:
        with clients_lock:
            for info in list(clients.values()):
                try:
                    send(info["conn"], {"type": "server_shutdown"})
                    info["conn"].close()
                except Exception:
                    pass
        with auctions_lock:
            for a in auctions.values():
                if a.get("timer"):
                    a["timer"].cancel()
        srv.close()
        print("[Server] Stopped.")


if __name__ == "__main__":
    main()
