"""Outer terminal detection.

Identifies the terminal emulator at the far end of the pipe (through SSH
and tmux passthrough) so the rest of the package can pick the right image
protocol. See `detect_terminal()` for the strategy hierarchy.
"""

from __future__ import annotations  # PEP 604 ``str | None`` on Python 3.9

import os
import re
import select
import termios
import tty
from functools import lru_cache


def query_terminal(sequence: str, timeout: float = 0.3) -> str:
    """Send an escape sequence and read the response via /dev/tty.

    Uses /dev/tty directly so it works even if stdin is piped. Wraps
    the query in tmux passthrough when inside tmux so the bytes reach the
    outer terminal. Returns the raw response, or "" if there's no
    response or no controlling tty.
    """
    if "TMUX" in os.environ:
        inner = sequence.replace("\033", "\033\033")
        sequence = f"\033Ptmux;{inner}\033\\"

    try:
        fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
    except OSError:
        return ""

    old_attrs = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        os.write(fd, sequence.encode())

        buf = b""
        while True:
            ready, _, _ = select.select([fd], [], [], timeout)
            if not ready:
                break
            buf += os.read(fd, 256)
            # Terminal responses end with ST (`ESC \`) for DCS, or `c` for
            # DA1/DA2-style replies.
            if buf.endswith(b"\033\\") or buf.endswith(b"c"):
                break
            if len(buf) > 512:  # safety limit on runaway responses
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
        os.close(fd)

    return buf.decode("ascii", errors="replace")


def _query_xtgettcap(cap: str) -> str | None:
    """Query a single XTGETTCAP capability and return its decoded value.

    Sends ``DCS + q <hex-name> ST`` and parses the
    ``DCS 1 + r <hex-name> = <hex-value> ST`` reply (a ``DCS 0 + r`` reply
    means the capability is unknown). Handles both terminfo names like ``TN``
    and kitty's ``kitty-query-*`` extension fields. Returns None if the
    terminal doesn't report the capability.
    """
    name_hex = cap.encode("ascii").hex()
    response = query_terminal(f"\033P+q{name_hex}\033\\")
    match = re.search(
        rf"\033P1\+r{name_hex}=([0-9a-fA-F]+)\033\\", response, re.IGNORECASE
    )
    if not match:
        return None
    try:
        return bytes.fromhex(match.group(1)).decode("ascii", errors="replace")
    except ValueError:
        return None


def _normalise(name: str | None) -> str | None:
    """Normalize a terminal name to a lowercase, version-free token.

    Different detection methods (and different terminals) report the same
    terminal under different shapes:
      - "kitty(0.32.0)"      (XTVERSION)
      - "Ghostty 1.0.0"      (XTVERSION)
      - "xterm-kitty"        (XTGETTCAP, $TERM)
      - "tmux-256color"      ($TERM inside tmux)
      - "xterm-256color"     ($TERM in plain xterm)
      - "iTerm.app"          ($TERM_PROGRAM)

    We normalize them all to a bare lowercase token so detect_terminal()
    returns a single canonical form regardless of which strategy hit.
    """
    if not name:
        return None

    # Drop a trailing version suffix: split at the first whitespace or '('
    # so "kitty(0.32.0)" → "kitty" and "Ghostty 1.0" → "Ghostty". re.split
    # always returns at least one element, so [0] is safe.
    name = re.split(r"[\s(]", name, maxsplit=1)[0]

    # Special case: "xterm-kitty" / "xterm-ghostty" pack the real terminal
    # name behind an xterm-compat prefix. When the part after "xterm-" is
    # pure letters, treat it as the name. With digits ("xterm-256color")
    # `xterm` IS the terminal and the suffix is a feature variant — fall
    # through to the generic first-segment rule below.
    m = re.fullmatch(r"xterm-([a-zA-Z]+)", name)
    if m:
        return m.group(1).lower()

    # Generic case: the terminal name is the first hyphen-separated
    # segment. "tmux-256color" → "tmux", "screen-256color" → "screen",
    # "xterm-256color" → "xterm", "alacritty" → "alacritty".
    return name.split("-", 1)[0].lower() or None


def _detect_via_xtgettcap() -> str | None:
    """Ask the terminal for its terminfo TN (terminal name) capability."""
    return _normalise(_query_xtgettcap("TN"))


def _detect_via_xtversion() -> str | None:
    """Ask the terminal to identify itself via XTVERSION."""
    response = query_terminal("\033[>0q")
    # Response: ESC P > | <name>(<version>) ESC \
    match = re.search(r"\033P>\|(.*?)\033\\", response, re.DOTALL)
    if not match:
        return None
    return _normalise(match.group(1).strip())


def _detect_via_term_program_env() -> str | None:
    """$TERM_PROGRAM env var. Doesn't survive SSH and not set by every
    terminal (kitty doesn't, for one), but useful when terminal queries
    didn't respond."""
    return _normalise(os.environ.get("TERM_PROGRAM", ""))


def _detect_via_term_env() -> str | None:
    """Last resort: parse $TERM. Rewritten to tmux-… inside tmux."""
    term = os.environ.get("TERM")
    if not term:
        return None
    return _normalise(term)


@lru_cache(maxsize=1)
def detect_terminal() -> str | None:
    """Identify the outer terminal.

    Returns a canonical name ("kitty", "ghostty", "wezterm", "vscode", ...) or
    None if no source gave a usable answer. Importantly, it detects Kitty and
    Ghostty reliably even over SSH and inside tmux.

    The result is cached per process — the terminal can't change underneath us.

    References:
    - XTGETTCAP: https://github.com/kovidgoyal/kitty/issues/957#issuecomment-420318828
    - XTVERSION: https://invisible-island.net/xterm/ctlseqs/ctlseqs.html
    - https://ucs-detect.readthedocs.io/results.html#terminal-capabilities
    """
    # XTGETTCAP — real-time terminfo query. Authoritative when it answers.
    if name := _detect_via_xtgettcap():
        return name

    # XTVERSION — real-time identity query. Authoritative *except* for
    # "xterm.js": that's the JS terminal library, not the host. Hosts
    # like VSCode embed it and add their own image layer on top, so the
    # library name underrepresents the terminal's capabilities.
    xtversion = _detect_via_xtversion()
    if xtversion and xtversion != "xterm.js":
        return xtversion

    # Env-var fallbacks reject a few names:
    #   - tmux / screen — multiplexers, not terminals. tmux overwrites
    #     $TERM_PROGRAM, and both rewrite $TERM with their own names.
    #   - kitty / ghostty — they answer XT queries, so if we reached this
    #     point and an env var still claims kitty/ghostty, the value is
    #     stale or misconfigured. Don't trust it against the queries
    #     that just came back empty.
    rejected = {"tmux", "screen", "kitty", "ghostty"}

    term_program = _detect_via_term_program_env()
    if term_program and term_program not in rejected:
        return term_program

    term = _detect_via_term_env()
    if term and term not in rejected:
        return term

    return None


def get_terminal_dpi() -> float | None:
    """The terminal's physical DPI, or None if it doesn't report one.

    Only kitty implements the ``kitty-query-dpi_x`` field. Ghostty speaks the
    kitty graphics protocol but not this XTGETTCAP extension (yet), so it —
    like every other terminal — is gated out and returns None, which callers
    treat as "no DPI scaling".
    """
    if detect_terminal() != "kitty":
        return None
    value = _query_xtgettcap("kitty-query-dpi_x")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


@lru_cache(maxsize=1)
def get_dpi_scale() -> float:
    """Factor by which the figure's render DPI (and, in tmux, the assumed cell
    size) is multiplied for the current terminal.

    Equals the terminal's device-pixel ratio. Returns 1.0 (no scaling) whenever
    the terminal reports no DPI — anything but kitty, or a failed query — so
    callers can apply it unconditionally.

    Cached: it costs a terminal round-trip and the display density doesn't
    change underneath us in practice.
    """
    REFERENCE_DPI = 96.0
    MIN_DPI_SCALE = 1.0
    MAX_DPI_SCALE = 3.0

    dpi = get_terminal_dpi()
    if dpi is None:
        return 1.0
    return max(MIN_DPI_SCALE, min(MAX_DPI_SCALE, dpi / REFERENCE_DPI))


def diagnostic() -> dict[str, str | float | None]:
    """Run every detection strategy plus the orchestrator and return all
    results. Useful for debugging terminal-identification issues."""
    strategies = (
        _detect_via_xtgettcap,
        _detect_via_xtversion,
        _detect_via_term_program_env,
        _detect_via_term_env,
    )
    return {
        **{s.__name__: s() for s in strategies},
        "detect_terminal": detect_terminal(),
        "get_terminal_dpi": get_terminal_dpi(),
        "get_dpi_scale": get_dpi_scale(),
    }


if __name__ == "__main__":
    info = diagnostic()
    width = max(len(name) for name in info)
    for name, value in info.items():
        print(f"{name:<{width}}  {value!r}")
