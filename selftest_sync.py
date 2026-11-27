"""Self-check for the widget/band synchronisation that caused the
'widget missing on one monitor until enable/disable' bug.

Run: python selftest_sync.py
Exercises sync_widgets() against a fake band list -- no monitors need to change.
"""
import os
import shutil
import sys

sys.argv = sys.argv[:1]
import netmonitorsimple as ns  # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (("  -> " + detail) if detail and not cond else ""))
    if not cond:
        FAILED.append(name)


class FakeBand:
    """Stand-in for a taskbar HWND: a real window so IsWindow() works."""

    def __init__(self, x, y, w=1920, h=48, with_start=True):
        # reuse the widget class already registered by netmonitorsimple, so no RegisterClass needed
        self.hwnd = ns.user32.CreateWindowExW(
            0, ns.CLASS_NAME, "fakeband", ns.POPUP, x, y, w, h, None, None, None, None)
        assert self.hwnd, "could not create fake band"
        self.has_start = with_start

    def __int__(self):
        return int(self.hwnd)

    def destroy(self):
        ns.user32.DestroyWindow(self.hwnd)


def install_fake_bands(fake_list):
    """Patch traybars() and place() so the test controls the band set."""
    ns.traybars = lambda: [int(b) for b in fake_list]

    def fake_place(band, winw):
        for b in fake_list:
            if int(b.hwnd) == int(band):
                L, T, R, B = ns._rect(band)
                return L + 8, T, winw, B - T
        return None

    ns.place = fake_place


def widget_bands():
    return sorted(int(wd.band) for wd in ns.widgets)



def with_real_taskbar():
    bands = ns.traybars()
    if not bands:
        check("real taskbar available", False, "traybars() kosong")
        return
    band = bands[0]
    wd = ns.Widget(band, ns.load_cfg())
    if not wd.create():
        check("widget created on real taskbar", False)
        return
    try:
        ns.user32.SetWindowPos(wd.hwnd, -1, 0, 0, 0, 0,
                               ns.SWP_NOMOVE | ns.SWP_NOSIZE | ns.SWP_NOACTIVATE)
        check("clean state: band not above widget", wd._band_is_above() is False)

        # this is what clicking the taskbar does: it is topmost too, so it comes up
        ns.user32.SetWindowPos(band, -1, 0, 0, 0, 0,
                               ns.SWP_NOMOVE | ns.SWP_NOSIZE | ns.SWP_NOACTIVATE)
        # Informational only: with another instance running, its own topmost widgets
        # interleave and the band may not end up directly above ours. The invariant
        # that matters is asserted below -- after raise_above_taskbar() the band must
        # not be covering us, reproduced or not.
        print("    (band above widget before fix: %s)" % wd._band_is_above())

        wd.raise_above_taskbar()
        check("raise_above_taskbar() puts widget back on top", wd._band_is_above() is False)

        wd.raise_above_taskbar()
        check("repeat call is a harmless no-op", wd._band_is_above() is False)
    finally:
        wd.destroy()


def main():
    # NEVER touch the user's real config: point the module at a throwaway file
    import tempfile
    global _real_cfg_path
    real = ns.CFG_PATH
    tmpdir = tempfile.mkdtemp(prefix="nsm_selftest_")
    ns.CFG_PATH = os.path.join(tmpdir, "config.json")
    try:
        return _run(real)
    finally:
        ns.CFG_PATH = real
        shutil.rmtree(tmpdir, ignore_errors=True)


def _run(real_cfg_path):
    ns.save_cfg(dict(ns.DEFAULT))
    # netmonitorsimple registers its window class inside main(); the test must do it itself
    import ctypes as ct
    wc = ns.WNDCLASS()
    wc.lpfnWndProc = ns.WNDPROC(lambda h, m, a, b: ns.user32.DefWindowProcW(h, m, a, b))
    wc.hInstance = ct.windll.kernel32.GetModuleHandleW(None)
    wc.lpszClassName = ns.CLASS_NAME
    ns.user32.RegisterClassW(ct.byref(wc))
    print("== baseline: 1 band -> 1 widget ==")
    a = FakeBand(-1280, 1026)
    install_fake_bands([a])
    ns.rebuild()
    check("1 widget for 1 band", len(ns.widgets) == 1, str(len(ns.widgets)))

    print("== monitor appears: 1 band -> 2 ==")
    b = FakeBand(0, 1032)
    install_fake_bands([a, b])
    ns.sync_widgets()
    check("2 widgets for 2 bands", len(ns.widgets) == 2, str(len(ns.widgets)))
    check("both bands attached", widget_bands() == sorted([int(a), int(b)]), str(widget_bands()))

    print("== sync is idempotent (no duplicate widgets) ==")
    ns.sync_widgets()
    ns.sync_widgets()
    check("still 2 widgets after repeated sync", len(ns.widgets) == 2, str(len(ns.widgets)))

    print("== monitor disappears: 2 bands -> 1 (the reported bug) ==")
    install_fake_bands([a])
    b.destroy()                      # band window really is gone
    ns.sync_widgets()
    check("1 widget left after band died", len(ns.widgets) == 1, str(len(ns.widgets)))
    check("survivor is band a", widget_bands() == [int(a)], str(widget_bands()))

    print("== monitor comes back: 1 band -> 2 again ==")
    c = FakeBand(1600, 0)
    install_fake_bands([a, c])
    ns.sync_widgets()
    check("widget re-attached without enable/disable", len(ns.widgets) == 2, str(len(ns.widgets)))

    print("== disabled config -> no widgets ==")
    cfg = ns.load_cfg()
    cfg["enabled"] = False
    ns.save_cfg(cfg)
    ns.sync_widgets()
    check("0 widgets when disabled", len(ns.widgets) == 0, str(len(ns.widgets)))

    print("== enabled again -> widgets return ==")
    cfg = ns.load_cfg()
    cfg["enabled"] = True
    ns.save_cfg(cfg)
    ns.sync_widgets()
    check("2 widgets when re-enabled", len(ns.widgets) == 2, str(len(ns.widgets)))

    print("== widget re-raises itself above its taskbar band ==")
    # Uses a REAL taskbar band: a synthetic band is not topmost, so it cannot
    # reproduce being raised above the widget.
    with_real_taskbar()

    print("== placement keeps full width on every real band ==")
    cfg = ns.load_cfg()
    want = ns.text_width(cfg)
    bad = []
    for b in ns.traybars():
        L, T, R, B = ns._rect(b)
        r = ns.place(b, want)
        if r[2] != want or r[0] < L or r[0] + r[2] > R:
            bad.append((ns._cls(b), L, R, r))
    check("every band gets the full widget width, inside its bounds", not bad, str(bad))

    print("== stale band object dropped by reposition() ==")
    victim = ns.widgets[0]
    victim.band_dummy = True
    # kill the band under the widget
    for bb in (a, c):
        if int(bb) == int(victim.band):
            bb.destroy()
    ok = victim.reposition()
    check("reposition() reports False for dead band", ok is False, repr(ok))

    print("== config change reaches ALREADY-BUILT widgets ==")
    ns.rebuild()                       # fresh widgets at default size
    before = [wd.w for wd in ns.widgets]
    w_new = ns.text_width({**ns.load_cfg(), "size": 26})
    cfg = ns.load_cfg()
    cfg["size"] = 26
    ns.save_cfg(cfg)
    ns.sync_widgets()
    after = [wd.w for wd in ns.widgets]
    check("every widget resized after a size change", all(w == w_new for w in after),
          f"before={before} after={after} want={w_new}")
    for wd in ns.widgets:
        wd.reposition()
    check("reposition() then applies the new width",
          all(wd.w == w_new for wd in ns.widgets),
          str([(wd.w, wd.pos) for wd in ns.widgets]))
    ns.save_cfg(dict(ns.DEFAULT))

    for wd in ns.widgets:
        wd.destroy()
    del ns.widgets[:]
    for bb in (a, c):
        try:
            bb.destroy()
        except Exception:
            pass
    ns.save_cfg(dict(ns.DEFAULT))

    print()
    if FAILED:
        print("FAILED:", len(FAILED), FAILED)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())