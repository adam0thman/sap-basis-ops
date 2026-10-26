#!/usr/bin/env python3
"""SAP Software Center client, X.509 passport auth, standard library only.

Drives curl through the SAP for Me SAML auto-POST chain so search -> qualify ->
download -> verify runs with no browser. The certificate passphrase lives only in
a 0600 curl config file, so it never reaches a command line, ps output or a log.

Setup (once):
    umask 077
    printf 'cert-type = "P12"\ncert = "%s:%s"\n' "$PFX_PATH" "$PFX_PASS" > ~/.sapdl.cfg

Usage:
    sapdl.py search "SUM 2.0"           # JSON lines of matching objects
    sapdl.py info   <ObjectKey>         # FileName, size, SHA-256, status
    sapdl.py get    <ObjectKey> <out>   # download + verify against ObjectSet.Checksum

Override the cookie jar with SAPDL_JAR. See SKILL.md section 5.
"""
import sys, os, re, json, subprocess, html, hashlib, urllib.parse

CFG = os.path.expanduser(os.environ.get("SAPDL_CFG", "~/.sapdl.cfg"))
JAR = os.path.expanduser(os.environ.get("SAPDL_JAR", "~/.cache/sapdl/cookies.txt"))
SVC = "https://launchpad.support.sap.com/services/odata/svt/swdcuisrv"


def curl(url, data=None, out=None):
    cmd = ["curl", "-K", CFG, "-sS", "-L", "-c", JAR, "-b", JAR,
           "-w", "\n%{http_code}|%{content_type}|%{url_effective}"]
    if data is not None:
        for k, v in data:
            cmd += ["--data-urlencode", "%s=%s" % (k, v)]
    if out:
        cmd += ["-o", out]
    cmd.append(url)
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=out is None)
    if r.returncode:
        err = r.stderr if isinstance(r.stderr, str) else r.stderr.decode(errors="replace")
        sys.exit("curl failed rc=%d: %s" % (r.returncode, err[:300]))
    txt = r.stdout if isinstance(r.stdout, str) else r.stdout.decode(errors="replace")
    body, meta = txt.rsplit("\n", 1)
    code, ctype, eff = meta.split("|", 2)
    return body, code, ctype, eff


FORM  = re.compile(r"<form[^>]*action=\"([^\"]+)\"[^>]*>(.*?)</form>", re.S | re.I)
INPUT = re.compile(r"<input[^>]*>", re.I)


def attr(tag, name):
    m = re.search(name + r"=\"([^\"]*)\"", tag, re.I)
    return html.unescape(m.group(1)) if m else None


def follow(url, out=None, max_hops=8):
    """curl -L follows redirects but does NOT submit HTML forms.

    The SAML chain is carried by auto-POST forms, so each one has to be parsed
    and re-posted by hand. Three hops in the normal case; max_hops is the guard
    against a redirect loop.
    """
    body, code, ctype, eff = curl(url, out=out)
    for _ in range(max_hops):
        if out and "html" not in ctype:
            return body, code, ctype
        if "html" not in ctype and not body.lstrip().startswith("<"):
            return body, code, ctype
        page = open(out, errors="replace").read() if out else body
        m = FORM.search(page)
        if not m:
            # JS hash-bootstrap page: retry the original URL now that cookies are set
            if "window.location.hash" in page:
                body, code, ctype, eff = curl(url, out=out)
                continue
            return page, code, ctype
        action = urllib.parse.urljoin(eff, html.unescape(m.group(1)))
        fields = [(attr(t, "name"), attr(t, "value") or "")
                  for t in INPUT.findall(m.group(2)) if attr(t, "name")]
        body, code, ctype, eff = curl(action, data=fields, out=out)
    sys.exit("gave up after %d form hops - check the certificate is valid and not expired" % max_hops)


def odata(path):
    sep = "&" if "?" in path else "?"
    body, code, ctype = follow("%s/%s%s$format=json" % (SVC, path, sep))
    try:
        return json.loads(body)["d"]
    except Exception:
        sys.exit("not JSON (HTTP %s, %s): %s" % (code, ctype, body[:200]))


def search(q):
    d = odata("SearchResultSet?SEARCH_STRING=" + urllib.parse.quote(q) +
              "&SEARCH_MAX_RESULT=500&RESULT_PER_PAGE=500")
    for r in d.get("results", []):
        print(json.dumps({k: r.get(k) for k in
                          ("Title", "Description", "Infotype", "Fastkey",
                           "ReleaseDate", "Platform", "Size")}))


def info(key):
    d = odata("ObjectSet('%s')" % key)
    print(json.dumps({k: d.get(k) for k in
                      ("FileName", "Title", "Description", "FileSize", "Checksum",
                       "Status", "StatusDescr", "ReleaseDate", "PatchLevel",
                       "PackageLevel")}, indent=1))
    return d


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest().upper()


def get(key, outfile):
    d = odata("ObjectSet('%s')" % key)
    tmp = outfile + ".part"
    follow("https://softwaredownloads.sap.com/file/%s" % key, out=tmp)

    # An expired cert or a stale session yields an HTML error page with HTTP 200.
    # The magic bytes are what actually distinguishes a file from a login page.
    with open(tmp, "rb") as f:
        head = f.read(8)
    if not head.startswith(b"CAR 2") and not head.startswith(b"PK"):
        sys.exit("download is not an archive (starts %r); left in %s" % (head, tmp))

    got, want = sha256(tmp), (d.get("Checksum") or "").upper()
    print("sha256", got, "expected", want or "(none published)",
          "MATCH" if got == want else "MISMATCH" if want else "UNVERIFIED")
    if want and got != want:
        sys.exit(1)
    os.replace(tmp, outfile)
    print("saved", outfile, os.path.getsize(outfile), "bytes")


if __name__ == "__main__":
    os.makedirs(os.path.dirname(JAR), mode=0o700, exist_ok=True)
    args = sys.argv[1:]
    cmds = {"search": (search, 1), "info": (info, 1), "get": (get, 2)}
    if not args or args[0] not in cmds or len(args) - 1 != cmds[args[0]][1]:
        sys.exit(__doc__)
    cmds[args[0]][0](*args[1:])
