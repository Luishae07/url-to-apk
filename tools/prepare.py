#!/usr/bin/env python3
"""Reads what was asked for (an issue form, a manual run or an API call), checks it, and turns the
template/ Android project into build/project: the website's address, name, colour and icon filled in."""
import hashlib, ipaddress, json, os, re, shutil, socket, sys, urllib.parse, urllib.request
from xml.sax.saxutils import escape

UA = "url-to-apk/1.0 (+https://github.com/Luishae07/url-to-apk)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "build", "project")


def fail(msg):
    print("::error::" + msg)
    sys.exit(1)


def setenv(**kw):
    path = os.environ.get("GITHUB_ENV")
    if path:
        with open(path, "a") as f:
            for k, v in kw.items():
                f.write(f"{k}={v}\n")


def read_request():
    name = os.environ.get("GITHUB_EVENT_NAME", "")
    event = json.load(open(os.environ["GITHUB_EVENT_PATH"])) if os.environ.get("GITHUB_EVENT_PATH") else {}
    if name == "issues":
        issue = event["issue"]
        fields, cur = {}, None
        for line in (issue.get("body") or "").splitlines():
            m = re.match(r"^###\s+(.*)$", line)
            if m:
                cur = m.group(1).strip().lower()
                fields[cur] = ""
            elif cur is not None:
                fields[cur] += line + "\n"
        def field(prefix):
            for k, v in fields.items():
                if k.startswith(prefix):
                    v = v.strip()
                    return "" if v == "_No response_" else v
            return ""
        return dict(url=field("website"), name=field("app name"), location=field("should").lower().startswith("yes"),
                    issue=str(issue["number"]), tag=f"apk-issue-{issue['number']}")
    if name == "repository_dispatch":
        p = event.get("client_payload") or {}
        return dict(url=str(p.get("url", "")), name=str(p.get("name", "")), location=str(p.get("location", "")).lower() in ("1", "true", "yes"),
                    issue="", tag=f"apk-run-{os.environ.get('GITHUB_RUN_ID', '0')}")
    return dict(url=os.environ.get("INPUT_URL", ""), name=os.environ.get("INPUT_NAME", ""),
                location=os.environ.get("INPUT_LOCATION", "").lower() == "true", issue="",
                tag=f"apk-run-{os.environ.get('GITHUB_RUN_ID', '0')}")


def clean_url(raw):
    raw = (raw or "").strip().split()[0] if (raw or "").strip() else ""
    if not raw:
        fail("No website address was given.")
    if not re.match(r"^[a-z][a-z0-9+.-]*://", raw, re.I):
        raw = "https://" + raw
    u = urllib.parse.urlparse(raw)
    if u.scheme.lower() == "http":
        u = u._replace(scheme="https")          # the app does not allow plain http
    if u.scheme.lower() != "https" or not u.hostname or len(raw) > 300:
        fail("Only https:// website addresses (up to 300 characters) can be turned into an app.")
    if u.username or u.password:
        fail("Addresses with a user name or password are not allowed.")
    host = u.hostname.lower()
    if "." not in host:
        fail("That does not look like a public website address.")
    try:
        for info in socket.getaddrinfo(host, u.port or 443, proto=socket.IPPROTO_TCP):
            if not ipaddress.ip_address(info[4][0]).is_global:
                fail("That address points to a private network, not a public website.")
    except socket.gaierror:
        fail(f"Could not find {host}. Is the address right?")
    url = urllib.parse.urlunparse(u._replace(fragment=""))
    return url.replace('"', "%22").replace("\\", "%5C"), host


def fetch(url, limit=600_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read(limit), r.headers.get("Content-Type", ""), r.geturl()


def pick_icon(html, base):
    best, best_score = None, -1
    for tag in re.findall(r"<link\b[^>]*>", html, re.I):
        rel = re.search(r'rel=["\']([^"\']+)["\']', tag, re.I)
        href = re.search(r'href=["\']([^"\']+)["\']', tag, re.I)
        if not rel or not href or "icon" not in rel.group(1).lower():
            continue
        size = re.search(r'sizes=["\'](\d+)x\d+', tag, re.I)
        score = int(size.group(1)) if size else 32
        if "apple-touch-icon" in rel.group(1).lower():
            score += 1000
        if href.group(1).lower().split("?")[0].endswith(".svg"):
            continue                           # Pillow cannot read SVG
        if score > best_score:
            best, best_score = urllib.parse.urljoin(base, href.group(1)), score
    return best or urllib.parse.urljoin(base, "/favicon.ico")


def make_icons(icon_bytes, letter, color_hex):
    from PIL import Image, ImageDraw, ImageFont
    import io
    sizes = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    img = None
    if icon_bytes:
        try:
            img = Image.open(io.BytesIO(icon_bytes)).convert("RGBA")
            if min(img.size) < 32:
                img = None
        except Exception:
            img = None
    if img is not None:
        side = max(img.size)
        sq = Image.new("RGBA", (side, side), (255, 255, 255, 255))   # logos on transparent: put them on white
        sq.alpha_composite(img, ((side - img.width) // 2, (side - img.height) // 2))
        img = sq
    else:
        side = 192
        c = tuple(int(color_hex[i:i + 2], 16) for i in (1, 3, 5)) if re.match(r"^#[0-9a-f]{6}$", color_hex, re.I) else (31, 41, 55)
        img = Image.new("RGBA", (side, side), c + (255,))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.load_default(size=110)
        except TypeError:
            font = ImageFont.load_default()
        d.text((side / 2, side / 2), letter.upper(), fill=(255, 255, 255, 255), font=font, anchor="mm")
    res = os.path.join(OUT, "app", "src", "main", "res")
    for dens, px in sizes.items():
        os.makedirs(os.path.join(res, f"mipmap-{dens}"), exist_ok=True)
        img.resize((px, px), Image.LANCZOS).convert("RGB").save(os.path.join(res, f"mipmap-{dens}", "ic_launcher.png"))
    return img is not None


def main():
    req = read_request()
    if req.get("issue"):
        setenv(ISSUE_NUMBER=req["issue"])
    url, host = clean_url(req["url"])
    html, ctype, final = "", "", url
    try:
        body, ctype, final = fetch(url)
        html = body.decode("utf-8", "ignore")
    except Exception as e:
        fail(f"Could not open {url}: {e}")

    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    name = req["name"] or (re.sub(r"\s+", " ", title.group(1)).strip() if title else "") or host
    name = re.sub(r"[^\w .\-+!]", "", name)[:30].strip() or host[:30]
    theme = re.search(r'<meta[^>]+name=["\']theme-color["\'][^>]+content=["\'](#[0-9a-fA-F]{3,8})["\']', html, re.I)
    color = theme.group(1) if theme else "#1f2937"
    if not re.match(r"^#[0-9a-fA-F]{6}$", color):
        color = "#1f2937"

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30] or re.sub(r"[^a-z0-9]+", "-", host).strip("-")
    parts = [re.sub(r"[^a-z0-9]", "", p) for p in host.split(".")]
    seg = "_".join(p for p in parts if p) or "site"
    if not seg[0].isalpha():
        seg = "s" + seg
    appid = f"com.webapp.{seg}.a{hashlib.sha1(url.encode()).hexdigest()[:6]}"

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(ROOT, "template"), OUT)

    icon_bytes = None
    try:
        icon_bytes, _, _ = fetch(pick_icon(html, final), 2_000_000)
    except Exception as e:
        print("no usable site icon:", e)
    used_site_icon = make_icons(icon_bytes, name[:1] or host[:1], color)

    perms = ('    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />\n'
             '    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />') if req["location"] else ""
    subs = {
        "app/build.gradle": {"__APPID__": appid},
        "app/src/main/AndroidManifest.xml": {"__LOCATION_PERMS__": perms},
        "app/src/main/res/values/strings.xml": {"__NAME__": escape(name).replace("'", "\\'")},
        "app/src/main/java/app/webwrap/MainActivity.java": {"__URL__": url, "__LOCATION__": "true" if req["location"] else "false", "__COLOR__": color},
    }
    for rel, table in subs.items():
        p = os.path.join(OUT, rel)
        text = open(p, encoding="utf-8").read()
        for k, v in table.items():
            text = text.replace(k, v)
        open(p, "w", encoding="utf-8").write(text)

    print(f"app: {name!r}  url: {url}  id: {appid}  colour: {color}  location: {req['location']}  site icon: {used_site_icon}")
    setenv(APP_NAME=name, APK_SLUG=slug, APP_ID=appid, TAG=req["tag"], SITE_URL=url)


if __name__ == "__main__":
    main()
