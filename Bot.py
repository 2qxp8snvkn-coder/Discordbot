import requests
import time
import json
import random
import sys
import re
import base64
import traceback
import asyncio
from datetime import datetime, timezone
from typing import Optional
import os 
import threading
import discord
from discord import app_commands
from config import BOT_TOKEN, PREFIX, EMBED_COLOR, REQUIRED_STATUS_TEXT

BaseLayoutView = getattr(discord.ui, "LayoutView", discord.ui.View)

base = "https://discord.com/api/v9"
poll_iv = 60
hb_iv = 20
auto_yes = True
dbg = True

tasks_ok = [
    "WATCH_VIDEO",
    "PLAY_ON_DESKTOP",
    "STREAM_ON_DESKTOP",
    "PLAY_ACTIVITY",
    "WATCH_VIDEO_ON_MOBILE",
]

class cfg:
    poll = poll_iv
    hb = hb_iv
    auto = auto_yes
    d = dbg


class user_db:
    path = os.path.join("db", "data.json")
    lock = threading.Lock()

    @staticmethod
    def _ensure():
        os.makedirs(os.path.dirname(user_db.path), exist_ok=True)
        if not os.path.exists(user_db.path):
            with open(user_db.path, "w", encoding="utf-8") as f:
                json.dump({"users": []}, f, indent=2)

    @staticmethod
    def load() -> dict:
        with user_db.lock:
            user_db._ensure()
            try:
                with open(user_db.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict) or not isinstance(data.get("users"), list):
                    return {"users": []}
                return data
            except Exception:
                return {"users": []}

    @staticmethod
    def save(data: dict) -> None:
        with user_db.lock:
            user_db._ensure()
            tmp = f"{user_db.path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, user_db.path)

    @staticmethod
    def get(uid: int) -> Optional[dict]:
        data = user_db.load()
        suid = str(uid)
        for u in data.get("users", []):
            if str(u.get("userid")) == suid:
                return u
        return None

    @staticmethod
    def upsert(username: str, userid: int, usertoken: str) -> None:
        data = user_db.load()
        users = data.get("users", [])
        suid = str(userid)
        changed = False
        for u in users:
            if str(u.get("userid")) == suid:
                u["username"] = username
                u["userid"] = suid
                u["usertoken"] = usertoken
                changed = True
                break
        if not changed:
            users.append({
                "username": username,
                "userid": suid,
                "usertoken": usertoken,
            })
        data["users"] = users
        user_db.save(data)

class scrape:
    fb = 504649
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

    @staticmethod
    def bn() -> int:
        try:
            print("fetching build from discord...")
            r = requests.get("https://discord.com/app", headers={"User-Agent": scrape.ua}, timeout=15)
            if r.status_code != 200:
                print(f"discord page {r.status_code}, using fallback")
                return scrape.fb
            scripts = re.findall(r'/assets/([a-f0-9]+)\.js', r.text)
            if not scripts:
                scripts_alt = re.findall(r'src="(/assets/[^"]+\.js)"', r.text)
                scripts = [s.split('/')[-1].replace('.js', '') for s in scripts_alt]
            if not scripts:
                print("no js assets, fallback")
                return scrape.fb
            for h in scripts[-5:]:
                try:
                    ar = requests.get(f"https://discord.com/assets/{h}.js", headers={"User-Agent": scrape.ua}, timeout=15)
                    m = re.search(r'buildNumber["\s:]+["\s]*(\d{5,7})', ar.text)
                    if m:
                        n = int(m.group(1))
                        print(f"build ok: {n}")
                        return n
                except Exception:
                    continue
            print(f"no build in assets, fallback {scrape.fb}")
            return scrape.fb
        except Exception as e:
            print(f"build scrape err: {e}, fallback {scrape.fb}")
            return scrape.fb

    @staticmethod
    def sp(n: int) -> str:
        o = {
            "os": "Windows",
            "browser": "Discord Client",
            "release_channel": "stable",
            "client_version": "1.0.9175",
            "os_version": "10.0.26100",
            "os_arch": "x64",
            "app_arch": "x64",
            "system_locale": "en-US",
            "browser_user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "discord/1.0.9175 Chrome/128.0.6613.186 "
                "Electron/32.2.7 Safari/537.36"
            ),
            "browser_version": "32.2.7",
            "client_build_number": n,
            "native_build_number": 59498,
            "client_event_source": None,
        }
        return base64.b64encode(json.dumps(o).encode()).decode()

class sess:
    def __init__(self, tok: str, bn: int):
        self.t = tok
        self.s = requests.Session()
        self.rl_lock = threading.Lock()
        self.rl_until = 0.0
        self.min_gap = 1.25
        self.last_req = 0.0
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "discord/1.0.9175 Chrome/128.0.6613.186 "
            "Electron/32.2.7 Safari/537.36"
        )
        self.s.headers.update({
            "Authorization": tok,
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": ua,
            "X-Super-Properties": scrape.sp(bn),
            "X-Discord-Locale": "en-US",
            "X-Discord-Timezone": "America/New_York",
            "Origin": "https://discord.com",
            "Referer": "https://discord.com/channels/@me",
        })

    def _wait_slot(self):
        with self.rl_lock:
            now = time.time()
            wait_for_rl = max(0.0, self.rl_until - now)
            wait_for_gap = max(0.0, (self.last_req + self.min_gap) - now)
            w = max(wait_for_rl, wait_for_gap)
            if w > 0:
                time.sleep(w)
            self.last_req = time.time()

    def _mark_rate_limited(self, retry_after: float):
        with self.rl_lock:
            self.rl_until = max(self.rl_until, time.time() + max(0.0, retry_after))

    @staticmethod
    def _retry_after_from_resp(r: requests.Response) -> float:
        try:
            j = r.json()
            if isinstance(j, dict) and j.get("retry_after") is not None:
                return float(j.get("retry_after", 2))
        except Exception:
            pass
        hdr = r.headers.get("X-RateLimit-Reset-After")
        if hdr:
            try:
                return float(hdr)
            except Exception:
                pass
        ra = r.headers.get("Retry-After")
        if ra:
            try:
                return float(ra)
            except Exception:
                pass
        return 2.0

    def _req(self, method: str, path: str, pl: Optional[dict] = None, **k) -> requests.Response:
        u = f"{base}{path}"
        k.setdefault("timeout", 15)
        tries = 8
        for at in range(1, tries + 1):
            self._wait_slot()
            if dbg:
                print(f"{method} {path} try {at}/{tries}")
            try:
                if method == "get":
                    r = self.s.get(u, **k)
                else:
                    r = self.s.post(u, json=pl, **k)
            except requests.exceptions.RequestException as e:
                if at == tries:
                    raise
                w = min(30.0, (1.8 * at) + random.uniform(0.4, 1.3))
                print(f"network err ({e}), retry in {w:.1f}s")
                time.sleep(w)
                continue
            if dbg:
                print(f"  {r.status_code} {len(r.content)}b")
            if r.status_code != 429:
                if r.status_code >= 500 and at < tries:
                    w = min(30.0, (1.8 * at) + random.uniform(0.4, 1.3))
                    print(f"server {r.status_code}, retry in {w:.1f}s")
                    time.sleep(w)
                    continue
                return r
            ra = self._retry_after_from_resp(r)
            # Add larger jitter and mark a hard cooldown window for this token/session.
            w = min(120.0, ra + random.uniform(1.0, 2.5))
            self._mark_rate_limited(w)
            print(f"rate limit {path}, retry in {w:.1f}s")
            if at == tries:
                return r
            time.sleep(w)
        return r

    def g(self, p: str, **k) -> requests.Response:
        return self._req("get", p, **k)

    def p(self, path: str, pl: Optional[dict] = None, **k) -> requests.Response:
        return self._req("post", path, pl=pl, **k)

    def ok(self) -> bool:
        try:
            r = self.g("/users/@me")
            if r.status_code == 200:
                u = r.json()
                nm = u.get("username", "?")
                print(f"logged in: {nm} id {u['id']}")
                return True
            print(f"bad token {r.status_code}")
            return False
        except Exception as e:
            print(f"connect err: {e}")
            return False

    def has_required_status(self, required_text: str) -> tuple[bool, str]:
        rt = (required_text or "").strip()
        if not rt:
            return True, ""
        try:
            r = self.g("/users/@me/settings")
            if r.status_code != 200:
                return False, f"status check failed ({r.status_code})"
            d = r.json() if r.content else {}
            cs = d.get("custom_status", {}) if isinstance(d, dict) else {}
            txt = ""
            if isinstance(cs, dict):
                txt = str(cs.get("text", "")).strip()
            if txt.lower() == rt.lower():
                return True, txt
            return False, txt
        except Exception:
            return False, ""

class qp:
    @staticmethod
    def u(d: Optional[dict], *ks):
        if d is None:
            return None
        for x in ks:
            if x in d:
                return d[x]
        return None

    @staticmethod
    def tc(q: dict) -> Optional[dict]:
        c = q.get("config", {})
        return qp.u(c, "taskConfig", "task_config", "taskConfigV2", "task_config_v2")

    @staticmethod
    def nm(q: dict) -> str:
        c = q.get("config", {})
        m = c.get("messages", {})
        n = qp.u(m, "questName", "quest_name")
        if n:
            return n.strip()
        g = qp.u(m, "gameTitle", "game_title")
        if g:
            return g.strip()
        an = c.get("application", {}).get("name")
        if an:
            return an
        return f"quest#{q.get('id', '?')}"

    @staticmethod
    def exp(q: dict) -> Optional[str]:
        c = q.get("config", {})
        return qp.u(c, "expiresAt", "expires_at")

    @staticmethod
    def us(q: dict) -> dict:
        x = qp.u(q, "userStatus", "user_status")
        return x if isinstance(x, dict) else {}

    @staticmethod
    def can(q: dict) -> bool:
        e = qp.exp(q)
        if e:
            try:
                dt = datetime.fromisoformat(e.replace("Z", "+00:00"))
                if dt <= datetime.now(timezone.utc):
                    return False
            except Exception:
                pass
        t = qp.tc(q)
        if not t or "tasks" not in t:
            return False
        ts = t["tasks"]
        return any(ts.get(x) is not None for x in tasks_ok)

    @staticmethod
    def in_(q: dict) -> bool:
        return bool(qp.u(qp.us(q), "enrolledAt", "enrolled_at"))

    @staticmethod
    def done(q: dict) -> bool:
        return bool(qp.u(qp.us(q), "completedAt", "completed_at"))

    @staticmethod
    def tt(q: dict) -> Optional[str]:
        t = qp.tc(q)
        if not t or "tasks" not in t:
            return None
        for x in tasks_ok:
            if t["tasks"].get(x) is not None:
                return x
        return None

    @staticmethod
    def need(q: dict) -> int:
        t = qp.tc(q)
        k = qp.tt(q)
        if not t or not k:
            return 0
        return t["tasks"][k].get("target", 0)

    @staticmethod
    def got(q: dict) -> float:
        k = qp.tt(q)
        if not k:
            return 0.0
        pr = qp.us(q).get("progress", {}) or {}
        return pr.get(k, {}).get("value", 0)

    @staticmethod
    def en_at(q: dict) -> Optional[str]:
        return qp.u(qp.us(q), "enrolledAt", "enrolled_at")

class run:
    def __init__(self, sx: sess):
        self.sx = sx
        self.did = set()

    def fq(self) -> list:
        try:
            r = self.sx.g("/quests/@me")
            if r.status_code == 200:
                d = r.json()
                if isinstance(d, dict):
                    qs = d.get("quests", [])
                    ex = d.get("excluded_quests", [])
                    bl = qp.u(d, "quest_enrollment_blocked_until")
                    if bl:
                        print(f"enroll blocked until {bl}")
                    if ex and dbg:
                        print(f"{len(ex)} excluded")
                    return qs
                if isinstance(d, list):
                    return d
                return []
            if r.status_code == 429:
                ra = r.json().get("retry_after", 10)
                print(f"rate limit wait {ra}s")
                time.sleep(ra)
                return self.fq()
            print(f"quest fetch {r.status_code}: {r.text[:200]}")
            return []
        except Exception as e:
            print(f"fetch quests: {e}")
            if dbg:
                traceback.print_exc()
            return []

    def en1(self, q: dict) -> bool:
        nm = qp.nm(q)
        qid = q["id"]
        for at in range(1, 4):
            try:
                r = self.sx.p(f"/quests/{qid}/enroll", {
                    "location": 11,
                    "is_targeted": False,
                    "metadata_raw": None,
                    "metadata_sealed": None,
                    "traffic_metadata_raw": q.get("traffic_metadata_raw"),
                    "traffic_metadata_sealed": q.get("traffic_metadata_sealed"),
                })
                if r.status_code == 429:
                    ra = r.json().get("retry_after", 5)
                    w = ra + 1
                    print(f"rate limit enroll {nm} try {at}/3 wait {w}s")
                    time.sleep(w)
                    continue
                if r.status_code in (200, 201, 204):
                    print(f"enrolled: {nm}")
                    return True
                print(f"enroll fail {nm} {r.status_code}: {r.text[:200]}")
                return False
            except Exception as e:
                print(f"enroll err {nm}: {e}")
                return False
        print(f"skip {nm} after 3 rate limits")
        return False

    def auto(self, qs: list) -> list:
        if not cfg.auto:
            return qs
        bad = [x for x in qs if not qp.in_(x) and not qp.done(x) and qp.can(x)]
        if not bad:
            return qs
        print(f"{len(bad)} not enrolled, auto-accept...")
        for x in bad:
            self.en1(x)
            time.sleep(3)
        time.sleep(2)
        return self.fq()

    def vid(self, q: dict):
        nm = qp.nm(q)
        qid = q["id"]
        sn = qp.need(q)
        sd = qp.got(q)
        eat = qp.en_at(q)
        if eat:
            ets = datetime.fromisoformat(eat.replace("Z", "+00:00")).timestamp()
        else:
            ets = time.time()
        print(f"video {nm} ({sd:.0f}/{sn}s)")
        mf = 10
        sp = 7
        iv = 1
        while sd < sn:
            ma = (time.time() - ets) + mf
            df = ma - sd
            ts = sd + sp
            if df >= sp:
                try:
                    r = self.sx.p(f"/quests/{qid}/video-progress", {
                        "timestamp": min(sn, ts + random.random())
                    })
                    if r.status_code == 200:
                        b = r.json()
                        if b.get("completed_at"):
                            print(f"done: {nm}")
                            return
                        sd = min(sn, ts)
                        print(f"  [{nm}] {sd:.0f}/{sn}s")
                    elif r.status_code == 429:
                        ra = r.json().get("retry_after", 5)
                        print(f"  rate limit wait {ra + 1}s")
                        time.sleep(ra + 1)
                        continue
                    else:
                        print(f"  video {r.status_code}: {r.text[:200]}")
                except Exception as e:
                    print(f"  err: {e}")
            if ts >= sn:
                break
            time.sleep(iv)
        try:
            self.sx.p(f"/quests/{qid}/video-progress", {"timestamp": sn})
        except Exception:
            pass
        print(f"done: {nm}")

    def hb(self, q: dict):
        nm = qp.nm(q)
        qid = q["id"]
        tt = qp.tt(q)
        sn = qp.need(q)
        sd = qp.got(q)
        left = max(0, sn - sd)
        print(f"{tt} {nm} (~{left // 60} min left)")
        pid = random.randint(1000, 30000)
        while sd < sn:
            try:
                r = self.sx.p(f"/quests/{qid}/heartbeat", {
                    "stream_key": f"call:0:{pid}",
                    "terminal": False,
                })
                if r.status_code == 200:
                    b = r.json()
                    pr = b.get("progress", {})
                    if pr and tt in pr:
                        sd = pr[tt].get("value", sd)
                    print(f"  [{nm}] {sd:.0f}/{sn}s")
                    if b.get("completed_at") or sd >= sn:
                        print(f"done: {nm}")
                        return
                elif r.status_code == 429:
                    ra = r.json().get("retry_after", 10)
                    print(f"  rate limit wait {ra + 1}s")
                    time.sleep(ra + 1)
                    continue
                else:
                    print(f"  hb {r.status_code}: {r.text[:200]}")
            except Exception as e:
                print(f"  hb err: {e}")
            time.sleep(cfg.hb)
        try:
            self.sx.p(f"/quests/{qid}/heartbeat", {
                "stream_key": f"call:0:{pid}",
                "terminal": True,
            })
        except Exception:
            pass
        print(f"done: {nm}")

    def act(self, q: dict):
        nm = qp.nm(q)
        qid = q["id"]
        sn = qp.need(q)
        sd = qp.got(q)
        left = max(0, sn - sd)
        print(f"activity {nm} (~{left // 60} min left)")
        sk = "call:0:1"
        while sd < sn:
            try:
                r = self.sx.p(f"/quests/{qid}/heartbeat", {
                    "stream_key": sk,
                    "terminal": False,
                })
                if r.status_code == 200:
                    b = r.json()
                    pr = b.get("progress", {})
                    if pr and "PLAY_ACTIVITY" in pr:
                        sd = pr["PLAY_ACTIVITY"].get("value", sd)
                    print(f"  [{nm}] {sd:.0f}/{sn}s")
                    if b.get("completed_at") or sd >= sn:
                        break
                elif r.status_code == 429:
                    ra = r.json().get("retry_after", 10)
                    print(f"  rate limit wait {ra + 1}s")
                    time.sleep(ra + 1)
                    continue
                else:
                    print(f"  hb {r.status_code}: {r.text[:200]}")
            except Exception as e:
                print(f"  err: {e}")
            time.sleep(cfg.hb)
        try:
            self.sx.p(f"/quests/{qid}/heartbeat", {
                "stream_key": sk,
                "terminal": True,
            })
        except Exception:
            pass
        print(f"done: {nm}")

    def one(self, q: dict):
        qid = q.get("id")
        nm = qp.nm(q)
        tt = qp.tt(q)
        if not tt:
            print(f"{nm} unsupported task, skip")
            return
        if qid in self.did:
            return
        print(f"--- start {nm} ({tt}) ---")
        if tt in ("WATCH_VIDEO", "WATCH_VIDEO_ON_MOBILE"):
            self.vid(q)
        elif tt in ("PLAY_ON_DESKTOP", "STREAM_ON_DESKTOP"):
            self.hb(q)
        elif tt == "PLAY_ACTIVITY":
            self.act(q)
        self.did.add(qid)

    def list_actionable(self, qs: list) -> list:
        return [
            x for x in qs
            if qp.in_(x) and not qp.done(x) and qp.can(x)
            and x.get("id") not in self.did
        ]

    def go(self):
        print("=" * 60)
        print("discord quest auto v3")
        print(f"auto-accept: {cfg.auto}  poll: {cfg.poll}s")
        print("=" * 60)
        cy = 0
        while True:
            cy += 1
            print(f"--- scan #{cy} ---")
            qs = self.fq()
            tot = len(qs)
            if not qs:
                print("no quests")
            else:
                ie = sum(1 for x in qs if qp.in_(x))
                dc = sum(1 for x in qs if qp.done(x))
                cc = sum(1 for x in qs if qp.can(x))
                print(f"total {tot} enrolled {ie} done {dc} completable {cc}")
                for x in qs:
                    nm = qp.nm(x)
                    t = qp.tt(x) or "?"
                    if qp.done(x):
                        st = "x"
                    elif qp.in_(x):
                        st = ">"
                    else:
                        st = "o"
                    print(f"  {st} {nm} [{t}]")
                qs = self.auto(qs)
                go = [
                    x for x in qs
                    if qp.in_(x) and not qp.done(x) and qp.can(x)
                    and x.get("id") not in self.did
                ]
                if go:
                    print(f"\n{len(go)} to finish:")
                    for x in go:
                        self.one(x)
                else:
                    print("nothing to do right now")
            print(f"\nwait {cfg.poll}s (ctrl+c stop)\n")
            time.sleep(cfg.poll)

class user_ctx:
    def __init__(self, tok: str, sx: sess, rn: run):
        self.tok = tok
        self.sx = sx
        self.rn = rn
        self.running = False


def _mk_bar(cur: int, total: int, width: int = 12) -> str:
    if total <= 0:
        return "[" + ("-" * width) + "]"
    ratio = max(0.0, min(1.0, cur / total))
    fill = int(ratio * width)
    return "[" + ("#" * fill) + ("-" * (width - fill)) + "]"


def _status_badge(status: str) -> str:
    if status == "done":
        return "done"
    if status == "running":
        return "running"
    return "pending"


def _add_v2_container(view: BaseLayoutView, title: str, body: str) -> None:
    """
    Try to render Discord components v2 container blocks.
    Falls back silently on older discord.py versions.
    """
    Container = getattr(discord.ui, "Container", None)
    TextDisplay = getattr(discord.ui, "TextDisplay", None)
    Separator = getattr(discord.ui, "Separator", None)
    if not Container or not TextDisplay:
        return
    try:
        children = [TextDisplay(content=f"## {title}\n{body}")]
        if Separator:
            children.append(Separator())
        view.add_item(Container(*children))
    except Exception:
        return


def _add_v2_action_row(view: BaseLayoutView, *items) -> None:
    ActionRow = getattr(discord.ui, "ActionRow", None)
    if not ActionRow:
        for item in items:
            view.add_item(item)
        return
    try:
        view.add_item(ActionRow(*items))
    except Exception:
        for item in items:
            view.add_item(item)


def _build_progress_view(updated_at: str, overall_line: str, quest_lines: str) -> BaseLayoutView:
    view = BaseLayoutView(timeout=900)
    Container = getattr(discord.ui, "Container", None)
    TextDisplay = getattr(discord.ui, "TextDisplay", None)
    Separator = getattr(discord.ui, "Separator", None)

    if not Container or not TextDisplay or not Separator:
        _add_v2_container(
            view,
            "Quest Progress",
            f"live quest report\nupdated: {updated_at}\n{overall_line}\n{quest_lines}",
        )
        return view

    try:
        view.add_item(
            Container(
                TextDisplay(content="## Quest Progress"),
                Separator(),  
                TextDisplay(content=f"live quest report\nupdated: {updated_at}"),
                Separator(),  
                TextDisplay(content=overall_line),
                Separator(),  
                TextDisplay(content=quest_lines or "- no quests selected"),
            )
        )
        return view
    except Exception:
        _add_v2_container(
            view,
            "Quest Progress",
            f"live quest report\nupdated: {updated_at}\n{overall_line}\n{quest_lines}",
        )
        return view


def _required_status_value() -> str:
    return (REQUIRED_STATUS_TEXT or "").strip()


def _required_status_hint() -> str:
    need = _required_status_value()
    if not need:
        return "status check: disabled"
    return f"required status text: `{need}`"


class connect_modal(discord.ui.Modal, title="Connect Discord Token"):
    token = discord.ui.TextInput(
        label="User Token",
        placeholder="Paste your Discord user token",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=400,
    )

    def __init__(self, bot_ref: "quest_bot"):
        super().__init__()
        self.bot_ref = bot_ref

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        tok = str(self.token.value).strip()
        if not tok:
            await interaction.followup.send("empty token, try again", ephemeral=True)
            return

        try:
            bn = await asyncio.to_thread(scrape.bn)
            sx = sess(tok, bn)
            ok = await asyncio.to_thread(sx.ok)
            if not ok:
                await interaction.followup.send("bad token, connect failed", ephemeral=True)
                return
            status_ok, current_status = await asyncio.to_thread(sx.has_required_status, REQUIRED_STATUS_TEXT)
            if not status_ok:
                need = (REQUIRED_STATUS_TEXT or "").strip()
                if need:
                    await interaction.followup.send(
                        f"set custom status text to `{need}` first, then connect again\n"
                        f"current status: `{current_status or 'empty'}`",
                        ephemeral=True,
                    )
                    return
            me = await asyncio.to_thread(lambda: sx.g("/users/@me"))
            me_name = "unknown"
            if me.status_code == 200:
                me_name = me.json().get("username", "unknown")
            self.bot_ref.user_sessions[interaction.user.id] = user_ctx(tok, sx, run(sx))
            await asyncio.to_thread(user_db.upsert, me_name, interaction.user.id, tok)
            done_view = BaseLayoutView(timeout=180)
            _add_v2_container(
                done_view,
                "Connection Confirmed",
                f"Logged in as **{me_name}**.\nUse **/quest** to open quest selector.",
            )
            await interaction.followup.send(view=done_view, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"connect err: {e}", ephemeral=True)


class connect_button(discord.ui.Button):
    def __init__(self, bot_ref: "quest_bot"):
        super().__init__(label="Connect", style=discord.ButtonStyle.success)
        self.bot_ref = bot_ref

    async def callback(self, interaction: discord.Interaction):
        ctx = self.bot_ref.user_sessions.get(interaction.user.id)
        if ctx:
            status_ok, current_status = await asyncio.to_thread(ctx.sx.has_required_status, REQUIRED_STATUS_TEXT)
            if not status_ok:
                await interaction.response.send_message(
                    f"set required custom status first: `{_required_status_value()}`\n"
                    f"current status: `{current_status or 'empty'}`",
                    ephemeral=True,
                )
                return
        await interaction.response.send_modal(connect_modal(self.bot_ref))


class connect_view(BaseLayoutView):
    def __init__(self, bot_ref: "quest_bot", body: str = "Click **Connect** button, then paste token in modal."):
        super().__init__(timeout=300)
        self.bot_ref = bot_ref
        _add_v2_container(
            self,
            "Quest Connector",
            f"{body}\n{_required_status_hint()}",
        )
        _add_v2_action_row(self, connect_button(bot_ref))


class quest_select(discord.ui.Select):
    def __init__(self, bot_ref: "quest_bot", uid: int, qs: list):
        self.bot_ref = bot_ref
        self.uid = uid
        self.q_by_id = {q.get("id"): q for q in qs}
        options = []
        for q in qs[:25]:
            nm = qp.nm(q)[:100]
            tt = qp.tt(q) or "UNKNOWN"
            need = qp.need(q)
            got = int(qp.got(q))
            options.append(discord.SelectOption(
                label=nm,
                description=f"{tt} | {got}/{need}s"[:100],
                value=q.get("id"),
            ))
        super().__init__(
            placeholder="Select one or more quests",
            min_values=1,
            max_values=max(1, len(options)),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.uid:
            await interaction.response.send_message("this menu is not for you", ephemeral=True)
            return

        ctx = self.bot_ref.user_sessions.get(self.uid)
        if not ctx:
            await interaction.response.send_message("session expired. run /connect again", ephemeral=True)
            return
        if ctx.running:
            await interaction.response.send_message("quest run already in progress. wait for it to finish", ephemeral=True)
            return
        status_ok, current_status = await asyncio.to_thread(ctx.sx.has_required_status, REQUIRED_STATUS_TEXT)
        if not status_ok:
            await interaction.response.send_message(
                f"required custom status missing. set `{_required_status_value()}` first.\n"
                f"current status: `{current_status or 'empty'}`",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        chosen_ids = list(dict.fromkeys(self.values))
        picked = [self.q_by_id[x] for x in chosen_ids if x in self.q_by_id]
        if not picked:
            await interaction.followup.send("no valid quests selected", ephemeral=True)
            return

        try:
            latest_for_validation = await asyncio.to_thread(ctx.rn.fq)
            latest_by_id = {q.get("id"): q for q in latest_for_validation}
            valid_picked = []
            skipped = 0
            for q in picked:
                qid = q.get("id")
                q_latest = latest_by_id.get(qid)
                if not q_latest:
                    skipped += 1
                    continue
                if qp.done(q_latest) or not qp.in_(q_latest) or not qp.can(q_latest):
                    skipped += 1
                    continue
                valid_picked.append(q_latest)

            if not valid_picked:
                await interaction.followup.send("selected quests are no longer actionable. run /quest again", ephemeral=True)
                return

            if skipped:
                await interaction.followup.send(
                    f"skipped {skipped} stale/invalid selection(s), running {len(valid_picked)} quest(s)",
                    ephemeral=True,
                )

            ctx.running = True

            async def _run_selected():
                for q in valid_picked:
                    await asyncio.to_thread(ctx.rn.one, q)

            def _progress_text(latest_quests: list) -> str:
                by_id = {x.get("id"): x for x in latest_quests}
                lines = []
                done_count = 0
                for q in valid_picked:
                    qid = q.get("id")
                    qq = by_id.get(qid, q)
                    nm = qp.nm(qq)
                    need = max(1, qp.need(qq))
                    got = int(qp.got(qq))
                    if qp.done(qq):
                        done_count += 1
                        got = need
                        st = "done"
                    elif qp.in_(qq):
                        st = "running"
                    else:
                        st = "pending"
                    pct = int((got / need) * 100) if need > 0 else 0
                    lines.append(
                        f"- **{nm}**\n"
                        f"  {_status_badge(st)}  |  **{pct}%** ({got}/{need}s)"
                    )
                total = len(valid_picked)
                overall = int((done_count / total) * 100) if total else 0
                updated = datetime.now().strftime("%H:%M:%S")
                overall_line = f"overall progress: **{overall}%**  ({done_count}/{total} done)"
                return updated, overall_line, "\n".join(lines)

            p_view = _build_progress_view(
                updated_at=datetime.now().strftime("%H:%M:%S"),
                overall_line="overall progress: **0%**  (0/0 done)",
                quest_lines="starting selected quests...",
            )
            prog_msg = await interaction.followup.send(view=p_view, ephemeral=True, wait=True)

            run_task = asyncio.create_task(_run_selected())
            while not run_task.done():
                status_ok_loop, current_status_loop = await asyncio.to_thread(
                    ctx.sx.has_required_status, REQUIRED_STATUS_TEXT
                )
                if not status_ok_loop:
                    run_task.cancel()
                    stop_view = _build_progress_view(
                        updated_at=datetime.now().strftime("%H:%M:%S"),
                        overall_line="overall progress: stopped",
                        quest_lines=(
                            f"status check failed during run.\n"
                            f"required: `{_required_status_value()}`\n"
                            f"current: `{current_status_loop or 'empty'}`"
                        ),
                    )
                    try:
                        await prog_msg.edit(view=stop_view)
                    except Exception:
                        pass
                    await interaction.followup.send(
                        "quest run stopped because required custom status was removed/changed",
                        ephemeral=True,
                    )
                    return
                latest = await asyncio.to_thread(ctx.rn.fq)
                updated, overall_line, quest_lines = _progress_text(latest)
                v = _build_progress_view(updated, overall_line, quest_lines)
                try:
                    await prog_msg.edit(view=v)
                except Exception:
                    pass
                await asyncio.sleep(4)

            await run_task
            latest = await asyncio.to_thread(ctx.rn.fq)
            updated, overall_line, quest_lines = _progress_text(latest)
            final_view = _build_progress_view(updated, overall_line, quest_lines)
            await prog_msg.edit(view=final_view)
        except Exception as e:
            await interaction.followup.send(f"quest run err: {e}", ephemeral=True)
        finally:
            ctx.running = False


class quest_view(BaseLayoutView):
    def __init__(self, bot_ref: "quest_bot", uid: int, qs: list, stats_text: str):
        super().__init__(timeout=600)
        _add_v2_container(
            self,
            "Quest Selector",
            f"{stats_text}\n{_required_status_hint()}\nSelect one or more quests from dropdown and submit.",
        )
        _add_v2_action_row(self, quest_select(bot_ref, uid, qs))


class quest_bot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.user_sessions: dict[int, user_ctx] = {}

    async def setup_hook(self):
        await self.tree.sync()

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content.startswith(PREFIX):
            return
        rest = message.content[len(PREFIX):].strip()
        if not rest:
            return
        cmd = rest.split()[0].lower()
        if cmd == "connect":
            await handle_connect_message(message)
        elif cmd == "quest":
            await handle_quest_message(message)


bot = quest_bot()


async def _quest_result(uid: int):
    """Shared quest lookup used by both /quest and the {PREFIX}quest text command.
    Returns a dict with either a plain "content" string or a ready "view"."""
    ctx = bot.user_sessions.get(uid)
    if not ctx:
        return {"content": f"not connected. run /connect or `{PREFIX}connect` first", "view": None}
    if ctx.running:
        return {"content": "quest run already in progress. please wait", "view": None}

    status_ok, current_status = await asyncio.to_thread(ctx.sx.has_required_status, REQUIRED_STATUS_TEXT)
    if not status_ok:
        return {
            "content": (
                f"required custom status missing. set `{_required_status_value()}` first.\n"
                f"current status: `{current_status or 'empty'}`"
            ),
            "view": None,
        }
    qs = await asyncio.to_thread(ctx.rn.fq)
    if not qs:
        return {"content": "no quests available right now", "view": None}

    avail = [x for x in qs if qp.can(x)]
    if not avail:
        return {"content": "quests found but none are completable right now", "view": None}

    qs = await asyncio.to_thread(ctx.rn.auto, qs)
    todo = await asyncio.to_thread(ctx.rn.list_actionable, qs)
    if not todo:
        done_cnt = sum(1 for x in qs if qp.done(x))
        enr_cnt = sum(1 for x in qs if qp.in_(x))
        comp_cnt = sum(1 for x in qs if qp.can(x))
        if done_cnt == len(qs):
            content = "all available quests are already completed"
        elif enr_cnt == 0 and comp_cnt > 0:
            content = "quests available but none enrolled yet. try /quest again in a moment"
        else:
            content = "no actionable quests right now (already working, done, or not eligible)"
        return {"content": content, "view": None}

    tot = len(qs)
    ie = sum(1 for x in qs if qp.in_(x))
    dc = sum(1 for x in qs if qp.done(x))
    cc = sum(1 for x in qs if qp.can(x))
    msg = (
        f"total {tot} | enrolled {ie} | done {dc} | completable {cc}\n"
        f"select quests to run ({len(todo)} available)"
    )
    return {"content": None, "view": quest_view(bot, uid, todo, msg)}


@bot.tree.command(name="connect", description="Connect your token via button modal")
async def connect_cmd(interaction: discord.Interaction):
    v = connect_view(bot, "Click **Connect** button, then paste token in modal.")
    await interaction.response.send_message(view=v, ephemeral=True)


async def handle_connect_message(message: discord.Message):
    v = connect_view(bot, "Click **Connect** button, then paste token in modal.")
    await message.channel.send(view=v)


@bot.tree.command(name="quest", description="Show available quests in multi-select layout")
async def quest_cmd(interaction: discord.Interaction):
    ctx = bot.user_sessions.get(interaction.user.id)
    if not ctx:
        await interaction.response.send_message("not connected. run /connect first", ephemeral=True)
        return
    if ctx.running:
        await interaction.response.send_message("quest run already in progress. please wait", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        result = await _quest_result(interaction.user.id)
        if result["view"] is not None:
            await interaction.followup.send(view=result["view"], ephemeral=True)
        else:
            await interaction.followup.send(result["content"], ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"quest list err: {e}", ephemeral=True)


async def handle_quest_message(message: discord.Message):
    uid = message.author.id
    ctx = bot.user_sessions.get(uid)
    if not ctx:
        await message.channel.send(f"not connected. run `{PREFIX}connect` first")
        return
    if ctx.running:
        await message.channel.send("quest run already in progress. please wait")
        return

    placeholder = await message.channel.send("checking quests...")
    try:
        result = await _quest_result(uid)
        if result["view"] is not None:
            await placeholder.edit(content=None, view=result["view"])
        else:
            await placeholder.edit(content=result["content"])
    except Exception as e:
        await placeholder.edit(content=f"quest list err: {e}")


def main():
    bt = BOT_TOKEN
    if not bt:
        print("set BOT_TOKEN in config.py and run again")
        sys.exit(1)
    print(f"bot starting... prefix={PREFIX} embed_color={EMBED_COLOR}")
    print("use /connect then /quest")
    bot.run(bt)

if __name__ == "__main__":
    main()
