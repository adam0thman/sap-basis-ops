#!/usr/bin/env python3
"""SAP Software Center client, X.509 passport auth, standard library only.

Drives curl through the SAP for Me SAML auto-POST chain so search -> qualify ->
download -> verify runs with no browser. The certificate passphrase lives only in
a 0600 curl config file, so it never reaches a command line, ps output or a log.

Setup (once):
    umask 077
    printf 'cert-type = "P12"\ncert = "%s:%s"\n' "$PFX_PATH" "$PFX_PASS" > ~/.sapdl.cfg

Usage:
    sapdl.py search "SUM 2.0"           # catalogue search -> JSON lines
    sapdl.py info   <ObjectKey>         # FileName, size, SHA-256, status
    sapdl.py tree   <ENR>               # add-on: BOTH delivery variants + Fastkeys
    sapdl.py get    <ObjectKey> <out>   # download, resumable, SHA-256 verified

Override with SAPDL_CFG / SAPDL_JAR / SAPDL_RETRIES. See SKILL.md section 5.
"""
import sys, os, re, json, subprocess, html, hashlib, urllib.parse

CFG     = os.path.expanduser(os.environ.get("SAPDL_CFG", "~/.sapdl.cfg"))
JAR     = os.path.expanduser(os.environ.get("SAPDL_JAR", "~/.cache/sapdl/cookies.txt"))
RETRIES = int(os.environ.get("SAPDL_RETRIES", "3"))
SVC     = "https://launchpad.support.sap.com/services/odata/svt/swdcuisrv"

# An auto-POST form page is a few KB. Anything larger on a hop we expect to buffer
# in memory means the chain went somewhere unexpected -- bail rather than pull a
# multi-GB payload into RAM. (curl enforces this from Content-Length, so it is a
# guard against the documented shape changing, not a hard ceiling.)
FORM_PAGE_MAX = 2 << 20

ARCHIVE_MAGIC = (b"CAR 2", b"PK")


class Transient(Exception):
    """A curl-level failure worth retrying (network drop, truncated transfer)."""


def warn(msg):
    # stdout carries JSON lines; diagnostics must not land in a caller's parser.
    sys.stderr.write("sapdl: %s\n" % msg)


def curl(url, data=None, out=None, resume=False, maxsize=None):
    cmd = ["curl", "-K", CFG, "-sS", "-L", "-c", JAR, "-b", JAR,
           "-w", "\n%{http_code}|%{content_type}|%{url_effective}"]
    if maxsize:
        cmd += ["--max-filesize", str(maxsize)]
    if resume:
        cmd += ["-C", "-"]
    for k, v in (data or []):
        cmd += ["--data-urlencode", "%s=%s" % (k, v)]
    if out:
        cmd += ["-o", out]
    cmd.append(url)

    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=out is None)
    # curl creates the jar 0644; it holds a live session cookie for the S-user.
    try:
        os.chmod(JAR, 0o600)
    except OSError:
        pass

    if r.returncode:
        err = r.stderr if isinstance(r.stderr, str) else r.stderr.decode(errors="replace")
        raise Transient("curl rc=%d: %s" % (r.returncode, err.strip()[:300]))

    txt = r.stdout if isinstance(r.stdout, str) else r.stdout.decode(errors="replace")
    body, meta = txt.rsplit("\n", 1)
    code, ctype, eff = meta.split("|", 2)
    return body, code, ctype, eff


FORM  = re.compile(r"<form[^>]*action=\"([^\"]+)\"[^>]*>(.*?)</form>", re.S | re.I)
INPUT = re.compile(r"<input[^>]*>", re.I)


def attr(tag, name):
    m = re.search(name + r"=\"([^\"]*)\"", tag, re.I)
    return html.unescape(m.group(1)) if m else None


def follow(url, out=None, resume=False, max_hops=8):
    """Walk the SAML auto-POST chain. curl -L follows redirects but does NOT
    submit HTML forms, so each form's action + inputs are re-POSTed by hand.

    The documented chain is three hops:
      1. GET  /file/<key>                  -> form carrying SAMLRequest
      2. POST accounts.sap.com/.../sso     -> form carrying SAMLResponse
      3. POST the tokengen action          -> the file itself

    Only hop 3 can be large, and it is identified by carrying SAMLResponse. Every
    other hop is buffered in memory, so `out` receives the payload and nothing
    else -- no HTML ever transits the output file.
    """
    body, code, ctype, eff = curl(url, maxsize=None if out is None else FORM_PAGE_MAX)
    for _ in range(max_hops):
        if "html" not in ctype and not body.lstrip().startswith("<"):
            return body, code, ctype       # JSON/plain: the OData path ends here

        m = FORM.search(body)
        if not m:
            # JS hash-bootstrap page: replay the original URL now that cookies are set
            if "window.location.hash" in body:
                body, code, ctype, eff = curl(url, maxsize=FORM_PAGE_MAX if out else None)
                continue
            return body, code, ctype

        action = urllib.parse.urljoin(eff, html.unescape(m.group(1)))
        fields = [(attr(t, "name"), attr(t, "value") or "")
                  for t in INPUT.findall(m.group(2)) if attr(t, "name")]

        if out and any(k == "SAMLResponse" for k, _ in fields):
            curl(action, data=fields, out=out, resume=resume)   # terminal hop -> file
            return None, "200", "application/octet-stream"

        body, code, ctype, eff = curl(action, data=fields,
                                      maxsize=FORM_PAGE_MAX if out else None)

    raise Transient("gave up after %d form hops" % max_hops)


def odata(path, _retried=False):
    sep = "&" if "?" in path else "?"
    body, code, ctype = follow("%s/%s%s$format=json" % (SVC, path, sep))
    try:
        return json.loads(body)["d"]
    except Exception:
        # A lapsed IdP session returns an HTML login page with HTTP 200. Drop the
        # jar and re-auth once -- an SP queue must not die on file 5 of 6.
        if not _retried and ("html" in ctype or body.lstrip().startswith("<")):
            warn("session looks lapsed, re-authenticating")
            try:
                os.unlink(JAR)
            except OSError:
                pass
            return odata(path, _retried=True)
        sys.exit("not JSON (HTTP %s, %s): %s" % (code, ctype, body[:200]))


SEARCH_FIELDS = ("Title", "Description", "Infotype", "Fastkey",
                 "ReleaseDate", "Platform", "Size")


def row_key(r):
    # Navigation nodes carry an empty Fastkey -- for those the event string is
    # what makes the row unique. See SKILL.md 2a.
    return r.get("Fastkey") or (r.get("Title"), r.get("SubtreeEvent"))


def search(q, page=None, max_pages=50):
    """Page through the result set, verifying at runtime that paging works.

    This service is event-driven and does not document a paging cursor; $filter
    is known to be ignored on sibling entity sets. So rather than trust $skip,
    each page is checked against what has already been seen: if the rows repeat,
    the service ignored $skip and the result set is simply capped -- say so on
    stderr instead of presenting a truncated list as complete.
    """
    page = page or int(os.environ.get("SAPDL_PAGE", "500"))
    seen, skip, shown = set(), 0, 0

    for _ in range(max_pages):
        d = odata("SearchResultSet?SEARCH_STRING=%s&SEARCH_MAX_RESULT=%d"
                  "&RESULT_PER_PAGE=%d&$skip=%d"
                  % (urllib.parse.quote(q), page, page, skip))
        rows = d.get("results", [])
        if not rows:
            return shown

        fresh = [r for r in rows if row_key(r) not in seen]
        for r in fresh:
            seen.add(row_key(r))
            print(json.dumps({k: r.get(k) for k in SEARCH_FIELDS}))
        shown += len(fresh)

        if not fresh or len(fresh) < len(rows):
            if skip:
                warn("service ignored $skip -- showing the first %d rows only; "
                     "narrow the search string" % shown)
            return shown
        if len(rows) < page:
            return shown                      # last page, short
        skip += len(rows)

    warn("stopped after %d pages (%d rows); narrow the search string" % (max_pages, shown))
    return shown


def info(key):
    d = odata("ObjectSet('%s')" % key)
    print(json.dumps({k: d.get(k) for k in
                      ("FileName", "Title", "Description", "FileSize", "Checksum",
                       "Status", "StatusDescr", "ReleaseDate", "PatchLevel",
                       "PackageLevel")}, indent=1))
    return d


# SWTYPSC is the delivery type. Both variants are near-identical in size and both
# are valid CAR archives -- only the node you descended through says which is
# which, so this lists both rather than making you pick blind. See SKILL.md 2a.
DELIVERY = [("N", "INSTALLATION  (SAINT install package)"),
            ("X", "EXCHANGE-UPGRADE (update an existing add-on)")]


def tree(enr, v="INST"):
    for swtypsc, label in DELIVERY:
        print("== %s  SWTYPSC=%s" % (label, swtypsc))
        d = odata("DownloadItemSet?_EVENT=LIST&EVENT=LIST&ENR=%s&SWTYPSC=%s"
                  "&PECCLSC=NONE&V=%s&TA=ACTUAL"
                  % (urllib.parse.quote(enr), swtypsc, v))
        rows = d.get("results", [])
        if not rows:
            print("   (no files -- check ENR, or V=MAINT for maintenance deliveries)")
        for r in rows:
            print("   %-22s %-20s %14s  %s" % (
                r.get("Title") or "", r.get("Fastkey") or "",
                r.get("Size") or r.get("FileSize") or "", r.get("Description") or ""))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest().upper()


def head_bytes(path, n=8):
    try:
        with open(path, "rb") as f:
            return f.read(n)
    except OSError:
        return b""


def get(key, outfile):
    d = odata("ObjectSet('%s')" % key)
    want = (d.get("Checksum") or "").upper()
    part = outfile + ".part"
    url = "https://softwaredownloads.sap.com/file/%s" % key

    for attempt in range(1, RETRIES + 1):
        # Resume only from bytes that are provably a partial archive. A .part left
        # by an older build could be an HTML page; appending to that silently
        # corrupts the result.
        resume = (os.path.exists(part) and os.path.getsize(part) > 0
                  and head_bytes(part).startswith(ARCHIVE_MAGIC))
        if os.path.exists(part) and not resume:
            os.unlink(part)
        try:
            follow(url, out=part, resume=resume)
            break
        except Transient as e:
            if "rc=33" in str(e) and os.path.exists(part):
                os.unlink(part)                      # server refused the range
                sys.stderr.write("resume unsupported, restarting from zero\n")
            if attempt == RETRIES:
                sys.exit("download failed after %d attempts: %s\n"
                         "partial file kept at %s" % (RETRIES, e, part))
            sys.stderr.write("attempt %d/%d failed (%s), retrying\n" % (attempt, RETRIES, e))

    # An expired cert or a lapsed session yields HTTP 200 with an HTML login page.
    # Magic bytes are what actually tell a file from a login page.
    head = head_bytes(part)
    if not head.startswith(ARCHIVE_MAGIC):
        sys.exit("not an archive (starts %r) -- certificate valid? left in %s" % (head, part))

    got = sha256(part)
    print("sha256", got, "expected", want or "(none published)",
          "MATCH" if got == want else "MISMATCH" if want else "UNVERIFIED")
    if want and got != want:
        sys.exit(1)
    os.replace(part, outfile)
    print("saved", outfile, os.path.getsize(outfile), "bytes")


if __name__ == "__main__":
    d = os.path.dirname(JAR)
    if d:
        os.makedirs(d, mode=0o700, exist_ok=True)
    args = sys.argv[1:]
    cmds = {"search": (search, 1), "info": (info, 1), "tree": (tree, 1), "get": (get, 2)}
    if not args or args[0] not in cmds or len(args) - 1 != cmds[args[0]][1]:
        sys.exit(__doc__)
    cmds[args[0]][0](*args[1:])
