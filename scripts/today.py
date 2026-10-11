"""
Tạo assets/neofetch-dark.svg và assets/neofetch-light.svg cho GitHub profile README.

  python scripts/today.py            # lấy số liệu thật từ GitHub (cần ACCESS_TOKEN)
  python scripts/today.py --demo     # dùng số liệu giả để xem trước bố cục

Biến môi trường:
  ACCESS_TOKEN  Token GitHub để gọi GraphQL API (API này bắt buộc xác thực).
                Trên Actions: secret ACCESS_TOKEN nếu có, không thì github.token
                (chỉ đếm repo public). Chạy trên máy: dùng `gh auth token`.
  USER_NAME     (tuỳ chọn) ghi đè GITHUB_USERNAME trong config.py
"""
import datetime
import hashlib
import json
import os
import sys
from html import escape
from pathlib import Path

import config

ROOT = Path(__file__).resolve().parent.parent   # thư mục gốc repo
OUT_DIR = ROOT / "assets"
CACHE_DIR = ROOT / "cache"
USER_NAME = os.environ.get("USER_NAME") or config.GITHUB_USERNAME
GRAPHQL = "https://api.github.com/graphql"


# ════════════════════════════════════════════════════════════════════════════
# Uptime
# ════════════════════════════════════════════════════════════════════════════
def uptime_text(since: datetime.datetime) -> str:
    from dateutil import relativedelta
    d = relativedelta.relativedelta(datetime.datetime.today(), since)
    plural = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"
    cake = " 🎂" if d.months == 0 and d.days == 0 else ""
    return f"{plural(d.years, 'year')}, {plural(d.months, 'month')}, {plural(d.days, 'day')}{cake}"


# ════════════════════════════════════════════════════════════════════════════
# GitHub GraphQL
# ════════════════════════════════════════════════════════════════════════════
class GitHub:
    def __init__(self, token: str, login: str):
        import requests
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"bearer {token}"
        self.login = login
        self.calls = 0

    def q(self, query: str, **variables):
        self.calls += 1
        r = self.s.post(GRAPHQL, json={"query": query, "variables": variables}, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"GitHub API {r.status_code}: {r.text[:300]}")
        body = r.json()
        if "errors" in body:
            raise RuntimeError(f"GitHub API errors: {body['errors']}")
        return body["data"]

    def user(self):
        d = self.q("""query($login:String!){ user(login:$login){
                id createdAt followers{totalCount} } }""", login=self.login)["user"]
        created = datetime.datetime.strptime(d["createdAt"][:10], "%Y-%m-%d")
        return d["id"], d["followers"]["totalCount"], created

    def repos(self, affiliations):
        """Tất cả repo theo affiliation: [{name, stars, commits}]"""
        out, cursor = [], None
        while True:
            d = self.q("""query($login:String!,$aff:[RepositoryAffiliation],$cursor:String){
              user(login:$login){ repositories(first:60, after:$cursor, ownerAffiliations:$aff){
                totalCount
                pageInfo{ hasNextPage endCursor }
                nodes{ nameWithOwner stargazerCount
                  defaultBranchRef{ target{ ... on Commit{ history{ totalCount } } } } } } } }""",
                       login=self.login, aff=affiliations, cursor=cursor)["user"]["repositories"]
            for n in d["nodes"]:
                ref = n["defaultBranchRef"]
                out.append({
                    "name": n["nameWithOwner"],
                    "stars": n["stargazerCount"],
                    "commits": ref["target"]["history"]["totalCount"] if ref else 0,
                })
            if not d["pageInfo"]["hasNextPage"]:
                return out
            cursor = d["pageInfo"]["endCursor"]

    def my_loc(self, repo: str, owner_id: str):
        """Cộng additions/deletions của các commit do mình viết trên nhánh mặc định."""
        owner, name = repo.split("/")
        add = dele = mine = 0
        cursor = None
        while True:
            d = self.q("""query($owner:String!,$name:String!,$cursor:String,$author:ID!){
              repository(owner:$owner, name:$name){ defaultBranchRef{ target{ ... on Commit{
                history(first:100, after:$cursor, author:{id:$author}){
                  pageInfo{ hasNextPage endCursor }
                  nodes{ additions deletions } } } } } } }""",
                       owner=owner, name=name, cursor=cursor, author=owner_id)
            ref = d["repository"]["defaultBranchRef"]
            if not ref:
                return add, dele, mine
            h = ref["target"]["history"]
            for c in h["nodes"]:
                add += c["additions"]
                dele += c["deletions"]
                mine += 1
            if not h["pageInfo"]["hasNextPage"]:
                return add, dele, mine
            cursor = h["pageInfo"]["endCursor"]


def collect_stats(gh: GitHub):
    owner_id, followers, created = gh.user()
    owned = gh.repos(["OWNER"])
    everything = gh.repos(["OWNER", "COLLABORATOR", "ORGANIZATION_MEMBER"])

    # Cache LOC theo repo: chỉ tính lại repo nào có số commit thay đổi.
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / (hashlib.sha256(USER_NAME.encode()).hexdigest()[:16] + ".json")
    cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    fresh = {}
    try:
        for r in everything:
            old = cache.get(r["name"])
            if old and old["commits"] == r["commits"]:
                fresh[r["name"]] = old
            else:
                a, d, m = gh.my_loc(r["name"], owner_id) if r["commits"] else (0, 0, 0)
                fresh[r["name"]] = {"commits": r["commits"], "add": a, "del": d, "mine": m}
    finally:
        # Lưu phần đã tính được kể cả khi bị lỗi giữa chừng (rate limit...)
        merged = {**cache, **fresh}
        merged = {k: v for k, v in merged.items() if k in {r["name"] for r in everything}}
        cache_file.write_text(json.dumps(merged, indent=1, sort_keys=True))

    loc_add = sum(v["add"] for v in fresh.values())
    loc_del = sum(v["del"] for v in fresh.values())
    return {
        "repos": len(owned),
        "contributed": len(everything),
        "stars": sum(r["stars"] for r in owned),
        "commits": sum(v["mine"] for v in fresh.values()),
        "followers": followers,
        "loc": loc_add - loc_del,
        "loc_add": loc_add,
        "loc_del": loc_del,
        "created": created,
    }


DEMO_STATS = {"repos": 24, "contributed": 41, "stars": 37, "commits": 1384,
              "followers": 18, "loc": 186_402, "loc_add": 241_977, "loc_del": 55_575,
              "created": datetime.datetime(2019, 6, 1)}


# ════════════════════════════════════════════════════════════════════════════
# ASCII art
# ════════════════════════════════════════════════════════════════════════════
FALLBACK_ART = r"""
  .----------------------------------.
  |  o o o        minh@workstation   |
  |----------------------------------|
  | ~ % ./bootstrap.sh               |
  |   [ok] tools   homebrew + mise   |
  |   [ok] shell   zsh + starship    |
  |   [ok] git     configuration     |
  |   [ok] docker  orbstack          |
  | ~ % doctor                       |
  |   all checks passed.             |
  | ~ % _                            |
  |                                  |
  '----------------------------------'
          \_____________________/
       ___/_____________________\___
      /  [][][][][][][][][][][][]  \
     /  [][][][][][][][][][][][][]  \
    /__[____][______________][____]__\
""".strip("\n").split("\n")

# Nhân vật ASCII gốc (tự vẽ): tóc bù xù, tai nghe, ngồi sau laptop.
# Phần HEAD sẽ gật gù, BUBBLE bật lên theo nhịp (CSS animation trong SVG).
CHAR_HEAD = r"""
         ,/\/\/\/\/\/\/\,
       ,/\/\/\/\/\/\/\/\/\,
      /\/\/'          '\/\/\
   .-|/\/|   __    __   |\/\|-.
   |#|\/ |  (--)  (--)  | \/|#|
   |#| \ |       ,      | / |#|
   '-'   |     \___/    |   '-'
          \            /
           '-.______.-'
""".strip("\n").split("\n")

CHAR_BODY = r"""
              |    |
       .------'    '------.
      /  .-----------------.\
     |   |                 | |
     |   |       </>       | |
     |   |                 | |
   __|___|_________________|_|__
  |_____________________________|
""".strip("\n").split("\n")


def bubble_lines(text: str, width: int = 22):
    """Đóng khung câu nói thành bong bóng thoại ASCII có đuôi trỏ xuống đầu nhân vật."""
    import textwrap
    rows = textwrap.wrap(text, width)
    w = max(len(r) for r in rows)
    out = ["      ." + "-" * (w + 3) + "."]
    out += [f"     (  {r.ljust(w)}  )" for r in rows]
    tail_at = 16   # cột của khe đuôi, nằm trên đỉnh đầu nhân vật
    out.append("      '" + "-" * (tail_at - 7) + ".  ." + "-" * (w + 6 - tail_at) + "'")
    out.append(" " * (tail_at + 1) + "\\|")
    return out


RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"


def image_to_ascii(path: Path, width: int, height: int, invert: bool):
    from PIL import Image, ImageOps
    img = Image.open(path).convert("L")
    img = ImageOps.exif_transpose(img) or img
    img = ImageOps.autocontrast(img, cutoff=2)
    # crop về tỉ lệ khung (ký tự cao ~2 lần rộng)
    target = width / (height * 2.0)
    w, h = img.size
    if w / h > target:
        nw = int(h * target)
        img = img.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / target)
        img = img.crop((0, max(0, (h - nh) // 3), w, max(0, (h - nh) // 3) + nh))
    img = img.resize((width, height))
    # Nền SVG tối: pixel sáng -> ký tự dày (nhiều "mực" sáng hơn)
    ramp = RAMP if not invert else RAMP[::-1]
    n = len(ramp) - 1
    return ["".join(ramp[px * n // 255] for px in (img.getpixel((x, y)) for x in range(width)))
            .rstrip() for y in range(height)]


def load_art():
    """Trả về danh sách (phần, dòng). phần ∈ bubble | head | body."""
    mode = getattr(config, "ART", "character")
    if mode == "image":
        return []
    if mode == "character":
        bubble = bubble_lines(config.BUBBLE_TEXT) if getattr(config, "BUBBLE_TEXT", "") else []
        return ([("bubble", l) for l in bubble] + [("head", l) for l in CHAR_HEAD]
                + [("body", l) for l in CHAR_BODY])
    p = ROOT / config.AVATAR_FILE
    if mode == "avatar" and p.exists():
        lines = image_to_ascii(p, config.ASCII_WIDTH, config.ASCII_HEIGHT, config.ASCII_INVERT)
    else:
        lines = FALLBACK_ART
    return [("body", l) for l in lines]



# ── Ảnh minh hoạ đã chuyển sẵn sang ASCII màu (scripts/art.json, tạo bằng make_art.py) ──
ART_FONT = 10      # px — chữ nhỏ để ảnh ASCII chi tiết hơn
ART_CW = 6.6       # độ rộng ký tự ước lượng ở 10px (có dư cho Consolas +9%)
ART_LH = 12


def image_art_fragment(c):
    """SVG cho chế độ ART='image': bong bóng thoại + 2 nhân vật nhún nhảy so le."""
    data = json.loads((Path(__file__).with_name("art.json")).read_text(encoding="utf-8"))
    grid, split = data["grid"], data.get("split") or 0
    cols = max(len(r) for r in grid)
    people = [(0, split), (split, cols)] if split else [(0, cols)]
    frag = []

    text = getattr(config, "BUBBLE_TEXT", "")
    top = 30
    if text:
        w = len(text)
        tail = int(cols * 0.62)                       # đuôi chỉ về người bên phải
        bub = ["." + "-" * (w + 4) + ".",
               "(  " + text + "  )",
               "'" + "-" * (tail - 1) + ".  ." + "-" * (w + 4 - tail - 3) + "'",
               " " * (tail + 1) + "\\|"]
        frag.append(f'<g class="bubble"><text x="15" fill="{c["value"]}" font-size="{ART_FONT + 1}px">')
        for i, l in enumerate(bub):
            frag.append(f'<tspan x="15" y="{top + i * (ART_LH + 1)}">{escape(l)}</tspan>')
        frag.append("</text></g>")
        top += len(bub) * (ART_LH + 1) + 4

    for idx, (a, b) in enumerate(people):
        frag.append(f'<g class="p{idx}"><text x="15" fill="{c["text"]}" font-size="{ART_FONT}px">')
        for y, row in enumerate(grid):
            # Mỗi người là một <text> đủ chiều rộng; cột của người kia thay bằng khoảng trắng
            segs, cur, buf = [], None, ""
            for x in range(cols):
                ch, col = row[x] if x < len(row) else (" ", None)
                if not (a <= x < b):
                    ch, col = " ", None
                if col != cur and buf:
                    segs.append((cur, buf)); buf = ""
                cur = col; buf += ch
            if buf:
                segs.append((cur, buf))
            if all(t.strip() == "" for _, t in segs):
                continue
            inner = "".join(f'<tspan fill="{k}">{escape(t)}</tspan>' if k else escape(t) for k, t in segs)
            frag.append(f'<tspan x="15" y="{top + y * ART_LH}">{inner}</tspan>')
        frag.append("</text></g>")
    width = 15 + max(cols, len(text) + 6) * ART_CW
    height = top + len(grid) * ART_LH
    return frag, width, height


# ════════════════════════════════════════════════════════════════════════════
# SVG rendering
# ════════════════════════════════════════════════════════════════════════════
THEMES = {   # tông violet/cyan, khớp với profile-hero.svg
    "dark": dict(bg="#111022", text="#E4E2F5", key="#C4B5FD", value="#5EEAD4",
                 dots="#4A4770", add="#4ADE80", dele="#FB7185"),
    "light": dict(bg="#F7F6FD", text="#1F1D2E", key="#6D28D9", value="#0F766E",
                  dots="#C9C4E6", add="#15803D", dele="#BE123C"),
}

CHAR_W = 9.6     # độ rộng ký tự monospace @16px
LINE_H = 20


def span(cls, s):
    return f'<tspan class="{cls}">{escape(s)}</tspan>'


def kv_line(key, value, width):
    """'Key: ........ value' canh phải trong `width` ký tự."""
    label = f"{key}:"
    gap = width - len(label) - len(value)
    dots = " " + "." * (gap - 2) + " " if gap >= 3 else " " * max(gap, 1)
    keyparts = label[:-1].split(".")
    keysvg = ".".join(span("key", k) for k in keyparts) + ":"
    return keysvg + span("cc", dots) + span("value", value)


def rule_line(title, width):
    t = f"{title} "
    return span("text", t) + span("cc", "-" * (width - len(t)))


def stats_lines(s, width):
    """Hai dòng thống kê kiểu: Repos: 24 {Contributed: 41} | Stars: 37"""
    f = lambda n: f"{n:,}"
    left1 = [("Repos", f"{f(s['repos'])} {{Contributed: {f(s['contributed'])}}}"), ("Stars", f(s["stars"]))]
    left2 = [("Commits", f(s["commits"])), ("Followers", f(s["followers"]))]
    out = []
    half = (width - 3) // 2
    for (k1, v1), (k2, v2) in (left1, left2):
        out.append(kv_line(k1, v1, half) + span("cc", " | ") + kv_line(k2, v2, width - half - 3))
    loc_val = f"{s['loc']:,} ( "
    loc_tail = f"{s['loc_add']:,}++, {s['loc_del']:,}-- )"
    label = "Lines of Code on GitHub:"
    gap = width - len(label) - len(loc_val) - len(loc_tail)
    dots = " " + "." * max(gap - 2, 0) + " " if gap >= 3 else " "
    out.append(span("key", label) + span("cc", dots) + span("value", loc_val)
               + span("add", f"{s['loc_add']:,}++") + span("value", ", ")
               + span("del", f"{s['loc_del']:,}--") + span("value", " )"))
    return out


def build_info(stats):
    W = config.LINE_WIDTH
    lines = [rule_line(config.HEADER, W)]
    uptime = uptime_text(config.UPTIME_SINCE or stats["created"])
    for i, sec in enumerate(config.SECTIONS):
        if i:
            lines.append("")
        for k, v in sec:
            v = v.replace("{uptime}", uptime)
            if v:
                lines.append(kv_line(k, v, W))
    contact = [(k, v) for k, v in config.CONTACT if v]
    if contact:
        lines += ["", rule_line("- Contact", W)]
        lines += [kv_line(k, v, W) for k, v in contact]
    lines += ["", rule_line("- GitHub Stats", W)]
    lines += stats_lines(stats, W)
    return lines


ANIM_CSS = """
.head { animation: nod 4s ease-in-out infinite; }
.bubble { opacity: 0; transform-box: fill-box; transform-origin: 30% 100%;
          animation: pop 4s ease-out infinite; }
.p0 { animation: hop 1.2s ease-in-out infinite; }
.p1 { animation: hop 1.2s ease-in-out infinite; animation-delay: -0.6s; }
@keyframes hop {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}
@keyframes nod {
  0%, 8%, 24%, 40%, 100% { transform: translateY(0); }
  16%, 32% { transform: translateY(7px); }
}
@keyframes pop {
  0%, 38% { opacity: 0; transform: scale(0.6); }
  44% { opacity: 1; transform: scale(1.06); }
  48%, 90% { opacity: 1; transform: scale(1); }
  96%, 100% { opacity: 0; transform: scale(0.9); }
}
@media (prefers-reduced-motion: reduce) {
  .head, .p0, .p1 { animation: none; } .bubble { animation: none; opacity: 1; }
}
"""


def render(theme, art, info):
    c = THEMES[theme]
    image_mode = getattr(config, "ART", "") == "image"
    if image_mode:
        img_frag, img_w, img_h = image_art_fragment(c)
        info_x = img_w + 30
        height = int(max(30 + len(info) * LINE_H + 10, img_h + 20))
        art = []
    else:
        art_w = max(len(l) for _, l in art)
        info_x = 15 + art_w * CHAR_W + 30
        rows = max(len(art), len(info))
        height = 30 + rows * LINE_H + 10
        art_y0 = 30 + (rows - len(art)) * LINE_H // 2
    width = int(info_x + config.LINE_WIDTH * CHAR_W + 20)

    out = [f'<?xml version="1.0" encoding="utf-8"?>',
           f'<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" font-family="ConsolasFallback,Consolas,monospace" '
           f'width="{width}px" height="{height}px" font-size="16px">',
           "<style>",
           "@font-face { src: local('Consolas'), local('Consolas Bold'); font-family: 'ConsolasFallback';"
           " font-display: swap; -webkit-size-adjust: 109%; size-adjust: 109%; }",
           f".key {{fill: {c['key']};}} .value {{fill: {c['value']};}} .add {{fill: {c['add']};}}"
           f" .del {{fill: {c['dele']};}} .cc {{fill: {c['dots']};}} .text {{fill: {c['text']};}}",
           f".say {{fill: {c['value']};}}",
           "text, tspan {white-space: pre;}",
           ANIM_CSS,
           "</style>",
           f'<rect width="{width}px" height="{height}px" fill="{c["bg"]}" rx="15"/>']
    if image_mode:
        out += img_frag
    # Gom các dòng liên tiếp cùng phần vào một nhóm <g> để animate riêng
    groups, i = [], 0
    for part, line in art:
        if not groups or groups[-1][0] != part:
            groups.append((part, []))
        groups[-1][1].append((art_y0 + i * LINE_H, line))
        i += 1
    for part, lines in groups:
        fill = c["value"] if part == "bubble" else c["text"]
        out.append(f'<g class="{part}"><text x="15" fill="{fill}">')
        for y, line in lines:
            out.append(f'<tspan x="15" y="{y}">{escape(line)}</tspan>')
        out.append("</text></g>")
    out.append(f'<text x="{info_x:.0f}" y="30" fill="{c["text"]}">')
    for i, line in enumerate(info):
        if line:
            out.append(f'<tspan x="{info_x:.0f}" y="{30 + i * LINE_H}">{line}</tspan>')
    out += ["</text>", "</svg>"]
    return "\n".join(out) + "\n"


def main():
    demo = "--demo" in sys.argv
    if demo:
        stats = DEMO_STATS
    else:
        token = os.environ.get("ACCESS_TOKEN")
        if not token:
            sys.exit("Thiếu ACCESS_TOKEN. Chạy với --demo để xem trước.")
        if USER_NAME == "YOUR_GITHUB_USERNAME":
            sys.exit("Hãy điền GITHUB_USERNAME trong scripts/config.py.")
        gh = GitHub(token, USER_NAME)
        stats = collect_stats(gh)
        print(f"GitHub API calls: {gh.calls}")
    print(json.dumps(stats, indent=2, default=str))

    art, info = load_art(), build_info(stats)
    OUT_DIR.mkdir(exist_ok=True)
    for theme in THEMES:
        (OUT_DIR / f"neofetch-{theme}.svg").write_text(render(theme, art, info), encoding="utf-8")
    print("Wrote assets/neofetch-dark.svg, assets/neofetch-light.svg")


if __name__ == "__main__":
    main()
