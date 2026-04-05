# Real-Time Auction System

A multi-client auction platform built with Python using raw TCP sockets and TLS encryption. Multiple users connect simultaneously, create auctions, place live bids, and receive instant updates — all without any third-party networking libraries.

---

## Files

| File | Purpose |
|---|---|
| `server.py` | Runs the auction server — handles all clients, auctions, and bids |
| `client_gui.py` | Graphical client — connect, bid, create auctions, and track your wins |
| `generate_cert.py` | Generates the TLS certificate used to encrypt all connections |

---

## Setup

### 1. Install the one dependency

```bash
pip install cryptography
```

### 2. Generate a TLS certificate

```bash
python generate_cert.py
```

This creates `server.crt` and `server.key`. The server will also attempt to auto-generate these on first run if OpenSSL is installed.

---

## Running

### Start the server

```bash
python server.py
```

### Launch a client (in a new terminal)

```bash
python client_gui.py
```

To connect to a remote server:

```bash
python client_gui.py <host> <port>
```

Multiple clients can run at the same time — open as many terminals as needed.

---

## How to Use the GUI

1. Enter the server host and port, then click **CONNECT**
2. To create an auction: fill in the item name, starting price, duration (seconds), and minimum bid increment, then click **CREATE**
3. Select your newly created auction from the list and click **START AUCTION**
4. Other connected clients will see the auction appear and can place bids
5. As the creator, you can **END NOW** to close the auction early, or add extra time with **+30s / +60s / +120s**
6. When an auction ends, the winner sees a popup showing what they won and at what price
7. All your wins are saved in the **MY WINS** tab

---

## Features

| Feature | Description |
|---|---|
| TLS Encryption | All traffic between client and server is encrypted end-to-end |
| Multiple Clients | Each client runs in its own thread — all handled independently |
| Auction Lifecycle | Auctions go through pending → active → ended with automatic timers |
| Anti-Sniping | A bid placed in the last 10 seconds extends the auction by 15 seconds |
| Creator Controls | Auction creators can end early or add time — bidders cannot bid on their own auction |
| Live Updates | All connected clients see new bids and auction events in real time |
| Win History | Winners get a popup and a persistent wins log in the MY WINS tab |
| Graceful Shutdown | Ctrl+C on the server notifies all connected clients before closing |

---

## Architecture

```
server.py
│
├── main()              Sets up TLS, binds the socket, accepts clients
├── handle_client()     One thread per connected client, reads incoming messages
├── handle_command()    Routes each command: list / create / start / bid / end_now / add_time / status
├── end_auction()       Called by timer (or creator) when an auction finishes
├── reset_timer()       Restarts the countdown timer after time extensions or anti-snipe
├── broadcast()         Sends a message to every connected client
├── send()              Sends one JSON message to one connection
└── time_remaining()    Calculates how many seconds are left in an active auction

client_gui.py
│
├── AuctionClient       Handles the TCP+TLS connection, send/receive, and background thread
├── AuctionApp          The main tkinter window — builds all UI panels and handles events
├── _dispatch()         Routes every incoming server message to the right UI update
├── _tick()             Runs every second to count down all active auction timers locally
├── _show_win_popup()   Displays the winner popup when you win an auction
└── _update_creator_ui() Shows or hides creator controls depending on which auction is selected
```

### Message Format

All messages are newline-delimited JSON sent over TCP with TLS. Example exchange:

```
Client → Server:  {"command": "bid", "auction_id": "a1b2c3d4", "amount": 150.0}
Server → Client:  {"type": "bid_response", "success": true, "message": "Bid $150.00 accepted!"}
Server → Others:  {"type": "new_high_bid", "auction_id": "a1b2c3d4", "amount": 150.0, ...}
```

---

## Notes

- The self-signed certificate is for development and local testing. Production deployments would require a CA-signed certificate.
- The client disables certificate hostname verification (`CERT_NONE`) intentionally, since we use a self-signed cert.
- All shared state on the server (auctions dictionary, clients dictionary) is protected with `threading.Lock` to prevent race conditions when multiple clients act simultaneously.
