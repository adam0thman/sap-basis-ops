#!/usr/bin/env python3
"""Self-check for sapdl.py: python3 test_sapdl.py

Stubs curl, so it exercises the form-chain walk, terminal-hop detection, resume
gating and archive sniffing without touching SAP or needing a certificate.
"""
import os, sys, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sapdl

IDP = "https://accounts.sap.com/saml2/idp/sso"
TOK = "https://origin-az.softwaredownloads.sap.com/tokengen/?file=K1&downloadId=D1"


def form(action, fields):
    inputs = "".join('<input type="hidden" name="%s" value="%s">' % kv for kv in fields)
    return '<html><body><form method="post" action="%s">%s</form></body></html>' % (action, inputs)


def chain(payload=b"CAR 2.01" + b"\x00" * 40, dest=None):
    """Return (stub_curl, calls) reproducing the documented 3-hop chain."""
    calls = []

    def stub(url, data=None, out=None, resume=False, maxsize=None):
        calls.append(dict(url=url, fields=[k for k, _ in (data or [])],
                          out=out, resume=resume, maxsize=maxsize))
        if data is None:                                    # hop 1: GET
            return form(IDP, [("SAMLRequest", "rq"), ("RelayState", "rs")]), "200", "text/html", url
        names = [k for k, _ in data]
        if "SAMLRequest" in names:                          # hop 2: POST to IdP
            return form(TOK, [("SAMLResponse", "rp"), ("RelayState", "rs")]), "200", "text/html", IDP
        if "SAMLResponse" in names:                         # hop 3: POST -> the file
            assert out, "terminal hop must stream to a file, not memory"
            mode = "ab" if resume else "wb"
            with open(out, mode) as f:
                f.write(payload)
            return "", "200", "application/octet-stream", TOK
        raise AssertionError("unexpected hop: %r" % names)

    return stub, calls


def expect_exit(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except SystemExit as e:
        return str(e.code)
    raise AssertionError("expected SystemExit")


def main():
    tmp = tempfile.mkdtemp()
    sapdl.JAR = os.path.join(tmp, "cookies.txt")
    orig = sapdl.curl

    # --- 1. the payload never shares a path with the HTML hops -----------------
    stub, calls = chain()
    sapdl.curl = stub
    out = os.path.join(tmp, "a.sar")
    sapdl.follow("https://softwaredownloads.sap.com/file/K1", out=out)
    assert len(calls) == 3, calls
    assert [c["out"] for c in calls] == [None, None, out], \
        "only the terminal hop may write to the output file: %r" % [c["out"] for c in calls]
    assert calls[0]["maxsize"] == sapdl.FORM_PAGE_MAX, "form hops must be size-bounded"
    assert calls[2]["maxsize"] is None, "payload hop must not be size-capped"
    assert open(out, "rb").read().startswith(b"CAR 2")

    # --- 2. OData path stays in memory and is not size-capped ------------------
    def json_stub(url, data=None, out=None, resume=False, maxsize=None):
        assert out is None and maxsize is None, "odata hop should be plain in-memory"
        return json.dumps({"d": {"results": [{"Title": "X"}]}}), "200", "application/json", url
    sapdl.curl = json_stub
    assert sapdl.odata("ObjectSet('K1')")["results"][0]["Title"] == "X"

    # --- 3. lapsed session: HTML with no form -> drop jar, re-auth once --------
    open(sapdl.JAR, "w").write("cookie")
    state = {"n": 0}

    def lapsed(url, data=None, out=None, resume=False, maxsize=None):
        state["n"] += 1
        if state["n"] == 1:
            return "<html>Session expired</html>", "200", "text/html", url
        return json.dumps({"d": {"ok": 1}}), "200", "application/json", url
    sapdl.curl = lapsed
    assert sapdl.odata("ObjectSet('K1')") == {"ok": 1}
    assert state["n"] == 2, "should have retried exactly once"
    assert not os.path.exists(sapdl.JAR), "stale jar must be removed before re-auth"

    # and it must not loop forever when re-auth also fails
    sapdl.curl = lambda *a, **k: ("<html>nope</html>", "200", "text/html", "u")
    assert "not JSON" in expect_exit(sapdl.odata, "ObjectSet('K1')")

    # --- 4. resume only from provable archive bytes ---------------------------
    part = os.path.join(tmp, "b.sar.part")

    open(part, "wb").write(b"CAR 2.01" + b"\x00" * 100)      # partial archive -> resume
    stub, calls = chain(dest=part)
    sapdl.curl = stub
    sapdl.RETRIES = 1
    sapdl.odata = lambda p, _retried=False: {"Checksum": None}
    sapdl.get("K1", os.path.join(tmp, "b.sar"))
    assert calls[2]["resume"] is True, "a partial archive must resume"

    open(part, "w").write("<html>login page</html>")          # stale HTML -> discard
    stub, calls = chain()
    sapdl.curl = stub
    sapdl.get("K1", os.path.join(tmp, "c.sar"))
    assert calls[2]["resume"] is False, "must not append to a stale HTML .part"

    # --- 5. a login page delivered as HTTP 200 is caught before hashing --------
    sapdl.curl = lambda u, data=None, out=None, resume=False, maxsize=None: (
        (open(out, "wb").write(b"<html>login</html>"), ("", "200", "text/html", u))[1]
        if out else (form(IDP, [("SAMLResponse", "rp")]), "200", "text/html", u))
    msg = expect_exit(sapdl.get, "K1", os.path.join(tmp, "d.sar"))
    assert "not an archive" in msg, msg

    sapdl.curl = orig
    print("all checks passed")


if __name__ == "__main__":
    main()
