import socket, ssl, threading, json, time, sys
import tkinter as tk
from tkinter import ttk

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9999

BG      = "#0A0C10"
BG2     = "#0F1218"
BG3     = "#151922"
BG4     = "#1A2030"
BORDER  = "#1E2840"
ACCENT  = "#E87820"
ACCENT2 = "#C45A08"
BLUE    = "#2E7DD4"
BLUE2   = "#1A5AAA"
GREEN   = "#18B870"
RED     = "#D43030"
MUTED   = "#3A4860"
TEXT    = "#C8D4E8"
DIM     = "#6878A0"

F_HEAD  = ("Georgia", 9, "bold")
F_BODY  = ("Georgia", 10)
F_MONO  = ("Courier New", 10)
F_BIG   = ("Georgia", 20, "bold")


class AuctionClient:
    # __init__
    def __init__(self, on_msg, on_disc):
        self.conn      = None
        self.bidder_id = None
        self.running   = False
        self.on_msg    = on_msg
        self.on_disc   = on_disc

    # connect
    def connect(self, host, port):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE
        try:
            raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw.settimeout(8)
            raw.connect((host, port))
            s = ctx.wrap_socket(raw, server_hostname=host)
            s.settimeout(None)
            self.conn    = s
            self.running = True
            threading.Thread(target=self._recv, daemon=True).start()
            return True, None
        except Exception as e:
            try: raw.close()
            except Exception: pass
            return False, str(e)

    # send
    def send(self, d):
        if self.conn:
            try: self.conn.sendall((json.dumps(d) + "\n").encode())
            except Exception: self.running = False

    # disconnect
    def disconnect(self):
        self.running = False
        if self.conn:
            try: self.conn.close()
            except Exception: pass
            self.conn = None

    # _recv
    def _recv(self):
        buf = ""
        try:
            while self.running:
                data = self.conn.recv(4096)
                if not data: break
                buf += data.decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        try: self.on_msg(json.loads(line))
                        except Exception: pass
        except Exception: pass
        finally:
            self.running = False
            self.on_disc()


# _entry
def _entry(parent, var=None, width=16, ph="", **kw):
    e = tk.Entry(parent, bg=BG3, fg=TEXT, insertbackground=ACCENT,
                 relief="flat", bd=0, font=F_BODY, textvariable=var,
                 width=width, highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=BLUE, **kw)
    if ph and var is None:
        e.insert(0, ph); e.config(fg=MUTED)
        e.bind("<FocusIn>",  lambda ev: (e.delete(0, "end"), e.config(fg=TEXT)) if e.get() == ph else None)
        e.bind("<FocusOut>", lambda ev: (e.insert(0, ph), e.config(fg=MUTED)) if not e.get() else None)
    return e


# _btn
def _btn(parent, text, cmd, color=ACCENT, fg=BG, **kw):
    def _dk(c):
        try:
            r, g, b = int(c[1:3],16), int(c[3:5],16), int(c[5:7],16)
            return f"#{max(0,r-30):02x}{max(0,g-30):02x}{max(0,b-30):02x}"
        except Exception:
            return c
    b = tk.Button(parent, text=text, command=cmd, bg=color, fg=fg,
                  activebackground=_dk(color), activeforeground=fg,
                  relief="flat", bd=0, font=("Georgia", 9, "bold"),
                  cursor="hand2", padx=10, pady=5, **kw)
    b.bind("<Enter>", lambda e: b.config(bg=_dk(color)))
    b.bind("<Leave>", lambda e: b.config(bg=color))
    return b


# _sep
def _sep(parent):
    return tk.Frame(parent, bg=BORDER, height=1)


# _label
def _label(parent, text="", fg=DIM, font=F_BODY, **kw):
    return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=fg, font=font, **kw)


class AuctionApp(tk.Tk):

    # __init__
    def __init__(self):
        super().__init__()
        self.title("Auction House")
        self.configure(bg=BG)
        self.minsize(1080, 700)
        self.geometry("1200x760")
        self.client      = AuctionClient(self._on_msg, self._on_disconnect)
        self.auctions    = {}
        self._end_epochs = {}
        self._connected  = False
        self._sel_aid    = None
        self._my_wins    = []
        self._build_ui()
        self._tick()

    # _build_ui
    def _build_ui(self):
        top = tk.Frame(self, bg=BG2)
        top.pack(fill="x")
        tk.Frame(top, bg=BLUE, width=4).pack(side="left", fill="y")
        _label(top, "  AUCTION HOUSE", fg=ACCENT, font=("Georgia", 16, "bold"),
               padx=10, pady=10).pack(side="left")
        self._status_var = tk.StringVar(value="● OFFLINE")
        self._status_lbl = tk.Label(top, textvariable=self._status_var,
                                    bg=BG2, fg=RED, font=("Courier New", 10, "bold"), padx=10)
        self._status_lbl.pack(side="right", padx=6)
        self._id_var = tk.StringVar()
        tk.Label(top, textvariable=self._id_var, bg=BG2, fg=MUTED,
                 font=("Courier New", 9), padx=6).pack(side="right")
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg=BG2, width=290)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        self._build_left(left)
        self._build_right(right)

    # _build_left
    def _build_left(self, p):
        tk.Frame(p, bg=BG2, height=10).pack(fill="x")
        sec = tk.Frame(p, bg=BG2, padx=14)
        sec.pack(fill="x")
        _label(sec, "SERVER", fg=DIM, font=F_HEAD).pack(anchor="w", pady=(4, 6))
        grid = tk.Frame(sec, bg=BG2)
        grid.pack(fill="x")
        self._host_var = tk.StringVar(value=DEFAULT_HOST)
        self._port_var = tk.StringVar(value=str(DEFAULT_PORT))
        for row, lbl, var, w in [(0, "Host", self._host_var, 13), (1, "Port", self._port_var, 7)]:
            _label(grid, lbl, fg=DIM, font=("Georgia", 8)).grid(row=row, column=0, sticky="w", pady=2)
            _entry(grid, var=var, width=w).grid(row=row, column=1, padx=(6, 0), sticky="ew", pady=2)
        grid.columnconfigure(1, weight=1)
        self._conn_btn = _btn(sec, "CONNECT", self._toggle_connect, color=BLUE)
        self._conn_btn.pack(fill="x", pady=(8, 4))
        _sep(p).pack(fill="x", padx=12, pady=4)
        hdr = tk.Frame(p, bg=BG2, padx=14)
        hdr.pack(fill="x")
        _label(hdr, "LIVE AUCTIONS", fg=DIM, font=F_HEAD).pack(side="left", pady=(4, 6))
        _btn(hdr, "↻", self._req_list, color=BG3, fg=DIM).pack(side="right", pady=4)
        tf = tk.Frame(p, bg=BG2, padx=8)
        tf.pack(fill="both", expand=True)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("A.Treeview", background=BG3, foreground=TEXT,
                        fieldbackground=BG3, rowheight=30, borderwidth=0, font=("Courier New", 9))
        style.configure("A.Treeview.Heading", background=BG, foreground=DIM,
                        font=("Georgia", 8, "bold"), borderwidth=0, relief="flat")
        style.map("A.Treeview", background=[("selected", BG4)], foreground=[("selected", ACCENT)])
        self._tree = ttk.Treeview(tf, style="A.Treeview",
                                   columns=("item", "bid", "st", "t"),
                                   show="headings", selectmode="browse")
        for col, hd, w, anc in [("item","Item",100,"w"),("bid","Bid",64,"e"),
                                  ("st","State",56,"center"),("t","Time",44,"e")]:
            self._tree.heading(col, text=hd)
            self._tree.column(col, width=w, anchor=anc)
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)
        self._tree.tag_configure("active",  foreground=GREEN)
        self._tree.tag_configure("ended",   foreground=MUTED)
        self._tree.tag_configure("pending", foreground=ACCENT)
        self._tree.tag_configure("mine",    foreground=BLUE)
        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        ab = tk.Frame(p, bg=BG2, padx=8, pady=6)
        ab.pack(fill="x")
        self._start_btn = _btn(ab, "▶  START AUCTION", self._start_selected, color=GREEN, fg=BG)
        self._start_btn.pack(fill="x")
        _sep(p).pack(fill="x", padx=12, pady=4)
        cf = tk.Frame(p, bg=BG2, padx=14, pady=4)
        cf.pack(fill="x")
        _label(cf, "CREATE AUCTION", fg=DIM, font=F_HEAD).pack(anchor="w", pady=(0, 6))
        self._c_item = _entry(cf, width=26, ph="Item name")
        self._c_item.pack(fill="x", pady=2)
        row = tk.Frame(cf, bg=BG2)
        row.pack(fill="x", pady=2)
        self._c_price = _entry(row, width=8, ph="Start $")
        self._c_price.pack(side="left", padx=(0, 3))
        self._c_dur = _entry(row, width=6, ph="Secs")
        self._c_dur.pack(side="left", padx=(0, 3))
        self._c_inc = _entry(row, width=5, ph="Inc $")
        self._c_inc.pack(side="left")
        _btn(cf, "CREATE  +", self._create_auction, color=ACCENT, fg=BG).pack(fill="x", pady=(8, 4))

    # _build_right
    def _build_right(self, p):
        self._card = tk.Frame(p, bg=BG2)
        self._card.pack(fill="x", padx=14, pady=(14, 0))
        row1 = tk.Frame(self._card, bg=BG2)
        row1.pack(fill="x", padx=16, pady=(14, 4))
        self._d_item = tk.Label(row1, text="Select an auction",
                                bg=BG2, fg=TEXT, font=("Georgia", 17, "bold"), anchor="w")
        self._d_item.pack(side="left")
        self._d_state_var  = tk.StringVar(value="")
        self._d_state_pill = tk.Label(row1, textvariable=self._d_state_var,
                                      bg=BG4, fg=MUTED, font=("Georgia", 9, "bold"), padx=10, pady=3)
        self._d_state_pill.pack(side="right")
        self._owner_badge = tk.Label(row1, text="  YOUR AUCTION  ",
                                     bg=BLUE, fg="white", font=("Georgia", 8, "bold"), padx=6, pady=3)
        stats = tk.Frame(self._card, bg=BG2)
        stats.pack(fill="x", padx=16, pady=(0, 8))
        self._d_bid    = self._stat(stats, "CURRENT BID", "$-",  TEXT, large=True)
        self._d_leader = self._stat(stats, "LEADER",      "-",   DIM)
        tf2 = tk.Frame(stats, bg=BG2, padx=14, pady=4)
        tf2.pack(side="left")
        _label(tf2, "TIME LEFT", fg=MUTED, font=("Georgia", 7, "bold")).pack(anchor="w")
        self._d_time_var = tk.StringVar(value="-")
        self._d_time_lbl = tk.Label(tf2, textvariable=self._d_time_var,
                                    bg=BG2, fg=ACCENT, font=F_BIG)
        self._d_time_lbl.pack(anchor="w")
        self._d_bids = self._stat(stats, "TOTAL BIDS", "0", DIM)
        self._d_id   = self._stat(stats, "AUCTION ID",  "-", MUTED)
        _sep(self._card).pack(fill="x", padx=14)
        self._bid_row = tk.Frame(self._card, bg=BG2, padx=16, pady=10)
        self._bid_row.pack(fill="x")
        _label(self._bid_row, "Your Bid  $", fg=DIM, font=F_BODY).pack(side="left")
        self._bid_amt = tk.StringVar()
        self._bid_entry = _entry(self._bid_row, var=self._bid_amt, width=12)
        self._bid_entry.pack(side="left", padx=(4, 10), ipady=3)
        self._bid_entry.bind("<Return>", lambda e: self._place_bid())
        self._bid_btn = _btn(self._bid_row, "PLACE BID  ↑", self._place_bid, color=BLUE)
        self._bid_btn.pack(side="left")
        self._no_bid_lbl = tk.Label(self._bid_row, text="  You cannot bid on your own auction",
                                    bg=BG2, fg=MUTED, font=("Georgia", 9, "italic"))
        _sep(self._card).pack(fill="x", padx=14)
        self._creator_frame = tk.Frame(self._card, bg=BG3, padx=16, pady=10)
        _label(self._creator_frame, "CREATOR CONTROLS", fg=BLUE,
               font=("Georgia", 8, "bold")).pack(anchor="w", pady=(0, 6))
        ctrl_row = tk.Frame(self._creator_frame, bg=BG3)
        ctrl_row.pack(fill="x")
        _btn(ctrl_row, "END NOW", self._end_now, color=RED, fg="white").pack(side="left", padx=(0, 6))
        _btn(ctrl_row, "+30s",  lambda: self._add_time(30),  color=BG4, fg=DIM).pack(side="left", padx=(0, 4))
        _btn(ctrl_row, "+60s",  lambda: self._add_time(60),  color=BG4, fg=DIM).pack(side="left", padx=(0, 4))
        _btn(ctrl_row, "+120s", lambda: self._add_time(120), color=BG4, fg=DIM).pack(side="left")
        tabs_hdr = tk.Frame(p, bg=BG, padx=14)
        tabs_hdr.pack(fill="x")
        self._wins_count_var = tk.StringVar(value="")
        self._tab_act_btn = tk.Button(tabs_hdr, text="BID ACTIVITY",
                                      command=lambda: self._switch_tab("activity"),
                                      bg=BG, fg=ACCENT, font=F_HEAD, relief="flat", bd=0,
                                      cursor="hand2", padx=4, pady=6,
                                      activebackground=BG, activeforeground=ACCENT)
        self._tab_act_btn.pack(side="left")
        self._tab_win_btn = tk.Button(tabs_hdr, text="MY WINS  \U0001f3c6",
                                      command=lambda: self._switch_tab("wins"),
                                      bg=BG, fg=MUTED, font=F_HEAD, relief="flat", bd=0,
                                      cursor="hand2", padx=14, pady=6,
                                      activebackground=BG, activeforeground=GREEN)
        self._tab_win_btn.pack(side="left")
        tk.Label(tabs_hdr, textvariable=self._wins_count_var,
                 bg=BG, fg=GREEN, font=("Courier New", 9)).pack(side="left")
        _btn(tabs_hdr, "CLEAR", self._clear_feed, color=BG3, fg=DIM).pack(side="right")
        self._tab_frame = tk.Frame(p, bg=BG, padx=14)
        self._tab_frame.pack(fill="both", expand=True, pady=(0, 6))
        self._feed_frame = tk.Frame(self._tab_frame, bg=BG)
        self._feed_frame.pack(fill="both", expand=True)
        self._feed = tk.Text(self._feed_frame, bg=BG, fg=DIM, font=F_MONO,
                              relief="flat", bd=0, wrap="word",
                              state="disabled", cursor="arrow", selectbackground=BG3)
        fsb = ttk.Scrollbar(self._feed_frame, orient="vertical", command=self._feed.yview)
        self._feed.configure(yscrollcommand=fsb.set)
        fsb.pack(side="right", fill="y")
        self._feed.pack(fill="both", expand=True)
        for tag, fg_col, font_cfg in [
            ("ts",     MUTED,  ("Courier New", 9)),
            ("ok",     GREEN,  F_MONO),
            ("reject", RED,    F_MONO),
            ("hi_bid", ACCENT, ("Courier New", 10, "bold")),
            ("ended",  GREEN,  ("Courier New", 10, "bold")),
            ("system", BLUE,   ("Georgia", 10, "bold")),
            ("err",    RED,    F_MONO),
            ("info",   DIM,    F_MONO),
            ("creator",BLUE,   ("Georgia", 9, "bold")),
        ]:
            self._feed.tag_configure(tag, foreground=fg_col, font=font_cfg)
        self._wins_frame = tk.Frame(self._tab_frame, bg=BG)
        ws = ttk.Style()
        ws.configure("W.Treeview", background=BG3, foreground=TEXT,
                     fieldbackground=BG3, rowheight=32, borderwidth=0, font=("Courier New", 10))
        ws.configure("W.Treeview.Heading", background=BG2, foreground=DIM,
                     font=("Georgia", 8, "bold"), borderwidth=0, relief="flat")
        ws.map("W.Treeview", background=[("selected", BG4)], foreground=[("selected", GREEN)])
        self._wins_tree = ttk.Treeview(self._wins_frame, style="W.Treeview",
                                        columns=("item", "price", "aid", "when"),
                                        show="headings", selectmode="browse")
        for col, hd, w, anc in [("item","Item Won",260,"w"),("price","Final Price",100,"e"),
                                  ("aid","Auction ID",80,"center"),("when","Time",80,"center")]:
            self._wins_tree.heading(col, text=hd)
            self._wins_tree.column(col, width=w, anchor=anc)
        wsb = ttk.Scrollbar(self._wins_frame, orient="vertical", command=self._wins_tree.yview)
        self._wins_tree.configure(yscrollcommand=wsb.set)
        wsb.pack(side="right", fill="y")
        self._wins_tree.pack(fill="both", expand=True)
        self._active_tab = "activity"
        self._toast_var = tk.StringVar()
        self._toast_lbl = tk.Label(p, textvariable=self._toast_var,
                                   bg=RED, fg="white", font=("Georgia", 9, "bold"), padx=12, pady=5)

    # _stat
    def _stat(self, parent, label, init, color, large=False):
        f = tk.Frame(parent, bg=BG2, padx=14, pady=4)
        f.pack(side="left")
        _label(f, label, fg=MUTED, font=("Georgia", 7, "bold")).pack(anchor="w")
        v = tk.StringVar(value=init)
        tk.Label(f, textvariable=v, bg=BG2, fg=color,
                 font=F_BIG if large else ("Courier New", 12)).pack(anchor="w")
        return v

    # _update_creator_ui
    def _update_creator_ui(self, aid):
        a        = self.auctions.get(aid, {})
        is_mine  = (a.get("creator_id") == self.client.bidder_id)
        state    = a.get("state", "")
        if is_mine:
            self._owner_badge.pack(side="right", padx=(6, 0))
        else:
            self._owner_badge.pack_forget()
        if is_mine and state == "active":
            self._creator_frame.pack(fill="x", padx=14, pady=(0, 4))
        else:
            self._creator_frame.pack_forget()
        if is_mine:
            self._bid_btn.pack_forget()
            self._bid_entry.pack_forget()
            self._no_bid_lbl.pack(side="left")
        else:
            self._no_bid_lbl.pack_forget()
            self._bid_entry.pack(side="left", padx=(4, 10), ipady=3)
            self._bid_btn.pack(side="left")
        if is_mine and state == "pending":
            self._start_btn.config(state="normal", bg=GREEN)
        else:
            self._start_btn.config(state="disabled", bg=MUTED)

    # _feed_append
    def _feed_append(self, text, tag="info"):
        ts = time.strftime("%H:%M:%S")
        self._feed.configure(state="normal")
        self._feed.insert("end", f"{ts}  ", "ts")
        self._feed.insert("end", text + "\n", tag)
        self._feed.see("end")
        self._feed.configure(state="disabled")

    # _clear_feed
    def _clear_feed(self):
        self._feed.configure(state="normal")
        self._feed.delete("1.0", "end")
        self._feed.configure(state="disabled")

    # _toast
    def _toast(self, text, color=RED):
        self._toast_var.set(f"  {text}  ")
        self._toast_lbl.config(bg=color)
        self._toast_lbl.place(relx=0.5, rely=0.97, anchor="s")
        self.after(3000, self._toast_lbl.place_forget)

    # _toggle_connect
    def _toggle_connect(self):
        if self._connected:
            self.client.disconnect()
            self._set_disconnected()
            return
        host = self._host_var.get().strip() or DEFAULT_HOST
        try: port = int(self._port_var.get())
        except ValueError: port = DEFAULT_PORT
        self._conn_btn.config(state="disabled", text="Connecting...")
        def _do():
            ok, err = self.client.connect(host, port)
            self.after(0, self._on_conn_result, ok, err)
        threading.Thread(target=_do, daemon=True).start()

    # _on_conn_result
    def _on_conn_result(self, ok, err):
        self._conn_btn.config(state="normal")
        if ok:
            self._connected = True
            self._conn_btn.config(text="DISCONNECT", bg=RED)
            self._conn_btn.bind("<Leave>", lambda e: self._conn_btn.config(bg=RED))
            self._status_var.set("● ONLINE")
            self._status_lbl.config(fg=GREEN)
            self._feed_append("Connected -- TLS active.", "system")
        else:
            self._conn_btn.config(text="CONNECT", bg=BLUE)
            self._toast(f"Connection failed: {err}")

    # _set_disconnected
    def _set_disconnected(self):
        self._connected = False
        self._conn_btn.config(text="CONNECT", bg=BLUE)
        self._conn_btn.bind("<Leave>", lambda e: self._conn_btn.config(bg=BLUE))
        self._status_var.set("● OFFLINE")
        self._status_lbl.config(fg=RED)
        self._id_var.set("")

    # _on_disconnect
    def _on_disconnect(self):
        self.after(0, self._set_disconnected)
        self.after(0, self._feed_append, "Disconnected from server.", "err")

    # _refresh_tree
    def _refresh_tree(self, lst):
        sel = self._sel_aid
        self._tree.delete(*self._tree.get_children())
        self.auctions.clear()
        for a in lst:
            aid     = a["id"]
            state   = a["state"]
            t_rem   = a.get("time_remaining") or 0
            bid_s   = f"${a['current_bid']:.2f}"
            t_str   = self._fmt_time(t_rem) if t_rem else "-"
            is_mine = (a.get("creator_id") == self.client.bidder_id)
            tag     = "mine" if is_mine else ("active" if state == "active" else
                                               "ended"  if state == "ended"  else "pending")
            self._tree.insert("", "end", iid=aid,
                               values=(a["item"][:16], bid_s, state, t_str), tags=(tag,))
            self.auctions[aid] = a
            if state == "active" and t_rem and aid not in self._end_epochs:
                self._end_epochs[aid] = time.time() + t_rem
        if sel and sel in self.auctions:
            try: self._tree.selection_set(sel)
            except Exception: pass

    # _patch_tree
    def _patch_tree(self, aid, bid=None, t_str=None):
        try:
            vals = list(self._tree.item(aid, "values"))
            if bid   is not None and len(vals) >= 2: vals[1] = bid
            if t_str is not None and len(vals) >= 4: vals[3] = t_str
            self._tree.item(aid, values=vals)
        except Exception: pass

    # _on_select
    def _on_select(self, _=None):
        sel = self._tree.selection()
        if not sel: return
        self._sel_aid = sel[0]
        if self._connected:
            self.client.send({"command": "status", "auction_id": self._sel_aid})

    # _apply_status
    def _apply_status(self, msg):
        state = msg["state"]
        aid   = msg["auction_id"]
        self._d_item.config(text=msg["item"])
        self._d_bid.set(f"${msg['current_bid']:.2f}")
        self._d_leader.set(msg.get("leader") or "-")
        self._d_bids.set(str(msg["bid_count"]))
        self._d_id.set(aid)
        colors = {"active": GREEN, "ended": MUTED, "pending": ACCENT}
        self._d_state_var.set(state.upper())
        self._d_state_pill.config(fg=colors.get(state, DIM))
        if state == "active":
            t_rem = float(msg.get("time_remaining", 0))
            self._end_epochs[aid] = time.time() + t_rem
            self._d_time_var.set(self._fmt_time(t_rem))
            self._set_time_color(t_rem)
        else:
            self._d_time_var.set("-")
            self._d_time_lbl.config(fg=MUTED)
        self.auctions[aid] = {**self.auctions.get(aid, {}), **msg}
        self._update_creator_ui(aid)

    # _tick
    def _tick(self):
        now = time.time()
        for aid, end_e in list(self._end_epochs.items()):
            rem   = max(0.0, end_e - now)
            t_str = self._fmt_time(rem)
            self._patch_tree(aid, t_str=t_str)
            if aid == self._sel_aid:
                self._d_time_var.set(t_str)
                self._set_time_color(rem)
            if rem <= 0:
                self._end_epochs.pop(aid, None)
        self.after(1000, self._tick)

    # _fmt_time
    @staticmethod
    def _fmt_time(secs):
        s = max(0, int(secs))
        if s >= 3600: return f"{s//3600}h {(s%3600)//60}m"
        if s >= 60:   return f"{s//60}m {s%60:02d}s"
        return f"{s}s"

    # _set_time_color
    def _set_time_color(self, secs):
        c = RED if secs < 10 else ACCENT if secs < 30 else GREEN
        self._d_time_lbl.config(fg=c)

    # _req_list
    def _req_list(self):
        if self._connected:
            self.client.send({"command": "list"})

    # _start_selected
    def _start_selected(self):
        if not self._sel_aid:
            self._toast("Select a pending auction first."); return
        if self._connected:
            self.client.send({"command": "start", "auction_id": self._sel_aid})

    # _place_bid
    def _place_bid(self):
        if not self._sel_aid:
            self._toast("Select an auction first."); return
        a = self.auctions.get(self._sel_aid, {})
        if a.get("creator_id") == self.client.bidder_id:
            self._toast("You cannot bid on your own auction."); return
        try:
            amount = float(self._bid_amt.get().strip())
        except ValueError:
            self._toast("Enter a valid bid amount."); return
        if amount <= 0:
            self._toast("Amount must be positive."); return
        if self._connected:
            self.client.send({"command": "bid", "auction_id": self._sel_aid, "amount": amount})
            self._bid_amt.set("")
        else:
            self._toast("Not connected.")

    # _end_now
    def _end_now(self):
        if not self._sel_aid:
            self._toast("No auction selected."); return
        if self._connected:
            self.client.send({"command": "end_now", "auction_id": self._sel_aid})

    # _add_time
    def _add_time(self, secs):
        if not self._sel_aid:
            self._toast("No auction selected."); return
        if self._connected:
            self.client.send({"command": "add_time", "auction_id": self._sel_aid, "seconds": secs})

    # _create_auction
    def _create_auction(self):
        def _v(w, ph):
            v = w.get().strip()
            return "" if v == ph else v
        item  = _v(self._c_item,  "Item name")
        price = _v(self._c_price, "Start $")
        dur   = _v(self._c_dur,   "Secs")
        inc   = _v(self._c_inc,   "Inc $") or "1.0"
        if not item:
            self._toast("Item name is required."); return
        try:
            p = float(price); d = int(dur); i = float(inc)
        except (ValueError, TypeError):
            self._toast("Price / Duration / Increment must be numbers."); return
        if not self._connected:
            self._toast("Not connected."); return
        self.client.send({"command": "create", "item": item,
                           "starting_price": p, "duration": d, "min_increment": i})
        for w, ph in [(self._c_item,"Item name"),(self._c_price,"Start $"),
                      (self._c_dur,"Secs"),(self._c_inc,"Inc $")]:
            w.delete(0, "end"); w.insert(0, ph); w.config(fg=MUTED)

    # _switch_tab
    def _switch_tab(self, tab):
        self._active_tab = tab
        if tab == "activity":
            self._wins_frame.pack_forget()
            self._feed_frame.pack(fill="both", expand=True)
            self._tab_act_btn.config(fg=ACCENT)
            self._tab_win_btn.config(fg=MUTED)
        else:
            self._feed_frame.pack_forget()
            self._wins_frame.pack(fill="both", expand=True)
            self._tab_act_btn.config(fg=MUTED)
            self._tab_win_btn.config(fg=GREEN)

    # _add_win
    def _add_win(self, item, price, aid):
        ts = time.strftime("%H:%M:%S")
        self._my_wins.append({"item": item, "price": price, "aid": aid, "time": ts})
        self._wins_tree.insert("", 0, values=(item, f"${price:.2f}", aid, ts))
        self._wins_count_var.set(f"  ({len(self._my_wins)})")
        self._tab_win_btn.config(fg=GREEN)

    # _show_win_popup
    def _show_win_popup(self, item, price, aid, total_bids):
        popup = tk.Toplevel(self)
        popup.title("You Won!")
        popup.configure(bg=BG2)
        popup.resizable(False, False)
        popup.grab_set()
        self.update_idletasks()
        x = self.winfo_x() + self.winfo_width()  // 2 - 220
        y = self.winfo_y() + self.winfo_height() // 2 - 160
        popup.geometry(f"440x320+{x}+{y}")
        tk.Frame(popup, bg=BLUE, height=4).pack(fill="x")
        tk.Label(popup, text="\U0001f3c6  YOU WON!", bg=BG2, fg=ACCENT,
                 font=("Georgia", 22, "bold"), pady=16).pack()
        tk.Frame(popup, bg=BORDER, height=1).pack(fill="x", padx=20)
        info = tk.Frame(popup, bg=BG2, pady=10)
        info.pack(fill="x", padx=30)
        def row(label, value, vc=TEXT):
            r = tk.Frame(info, bg=BG2)
            r.pack(fill="x", pady=4)
            tk.Label(r, text=label, bg=BG2, fg=MUTED,
                     font=("Georgia", 9, "bold"), width=14, anchor="w").pack(side="left")
            tk.Label(r, text=value, bg=BG2, fg=vc,
                     font=("Georgia", 12, "bold"), anchor="w").pack(side="left")
        row("Item", item)
        row("Final Price", f"${price:.2f}", GREEN)
        row("Auction ID", aid, DIM)
        row("Total Bids", str(total_bids), DIM)
        row("Won At", time.strftime("%H:%M:%S"), DIM)
        tk.Frame(popup, bg=BORDER, height=1).pack(fill="x", padx=20, pady=(6, 0))
        btn_row = tk.Frame(popup, bg=BG2, pady=14)
        btn_row.pack()
        _btn(btn_row, "VIEW MY WINS", lambda: (popup.destroy(), self._switch_tab("wins")),
             color=GREEN, fg=BG).pack(side="left", padx=6)
        _btn(btn_row, "CLOSE", popup.destroy, color=BG4, fg=DIM).pack(side="left", padx=6)

    # _on_msg
    def _on_msg(self, msg):
        self.after(0, self._dispatch, msg)

    # _dispatch
    def _dispatch(self, msg):
        t = msg.get("type", "")

        if t == "welcome":
            self.client.bidder_id = msg["bidder_id"]
            self._id_var.set(f"ID: {msg['bidder_id']}")
            self._feed_append(f"Welcome!  Your Bidder ID: {msg['bidder_id']}", "system")
            self.client.send({"command": "list"})

        elif t == "auction_list":
            self._refresh_tree(msg["auctions"])

        elif t == "auction_created":
            aid = msg["auction_id"]
            self._feed_append(f"Auction created -- ID: {aid}  (select it, then START)", "ok")
            self.client.send({"command": "list"})

        elif t == "auction_started":
            aid = msg["auction_id"]
            self._feed_append(f"Auction {aid} started -- '{msg.get('item','')}' is live!", "system")
            self.client.send({"command": "list"})

        elif t == "new_auction":
            self._feed_append(
                f"New auction: '{msg.get('item','')}' -- ${msg.get('starting_price',0):.2f} start", "info")
            self.client.send({"command": "list"})

        elif t == "bid_response":
            if msg["success"]:
                self._feed_append(f"Bid accepted: {msg['message']}", "ok")
                self._toast(msg["message"], GREEN)
            else:
                self._toast(msg["message"])
                self._feed_append(f"Bid rejected: {msg['message']}", "reject")
            self.client.send({"command": "list"})

        elif t == "new_high_bid":
            aid    = msg["auction_id"]
            amount = msg["amount"]
            bidder = msg["bidder_id"]
            t_rem  = msg.get("time_remaining", "?")
            label  = "YOU" if bidder == self.client.bidder_id else bidder
            self._feed_append(f"New high bid: {aid}  ${amount:.2f}  by {label}  ({t_rem}s left)", "hi_bid")
            self._patch_tree(aid, bid=f"${amount:.2f}")
            if self._sel_aid == aid:
                self._d_bid.set(f"${amount:.2f}")
                self._d_leader.set(label)
                try: self._end_epochs[aid] = time.time() + float(t_rem)
                except Exception: pass

        elif t == "time_added":
            aid   = msg["auction_id"]
            added = msg["added"]
            t_rem = msg.get("time_remaining", 0)
            self._feed_append(f"+{added}s added to {aid}  ({t_rem}s remaining)", "creator")
            self._end_epochs[aid] = time.time() + float(t_rem)
            if self._sel_aid == aid:
                self._d_time_var.set(self._fmt_time(t_rem))
                self._set_time_color(t_rem)

        elif t == "auction_ended":
            aid    = msg["auction_id"]
            winner = msg["winner"] or "No winner"
            price  = msg["final_price"]
            mine   = (winner == self.client.bidder_id)
            suffix = "  YOU WON!" if mine else ""
            self._feed_append(
                f"ENDED  {msg['item']}  --  {winner} @ ${price:.2f}  "
                f"({msg['total_bids']} bids){suffix}", "ended")
            self._end_epochs.pop(aid, None)
            self.client.send({"command": "list"})
            if self._sel_aid == aid:
                self._d_state_var.set("ENDED")
                self._d_state_pill.config(fg=MUTED)
                self._d_time_var.set("-")
                self._creator_frame.pack_forget()
            if mine:
                self._add_win(msg["item"], price, aid)
                self._show_win_popup(msg["item"], price, aid, msg["total_bids"])

        elif t == "auction_status":
            self._apply_status(msg)

        elif t == "server_shutdown":
            self._feed_append("Server is shutting down.", "err")

        elif t == "error":
            self._toast(msg["message"])
            self._feed_append(f"Error: {msg['message']}", "err")

    # on_close
    def on_close(self):
        self.client.disconnect()
        self.destroy()

# main loop
if __name__ == "__main__":
    app = AuctionApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    if len(sys.argv) >= 3:
        app._host_var.set(sys.argv[1])
        app._port_var.set(sys.argv[2])
    elif len(sys.argv) == 2:
        app._host_var.set(sys.argv[1])
    app.mainloop()
