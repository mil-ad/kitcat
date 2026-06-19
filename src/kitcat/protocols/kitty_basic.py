"""Basic kitty graphics protocol — transmit and display in one shot.

Used for terminals that implement kitty graphics but don't speak the Unicode
placeholder dialect (WezTerm, Konsole, st-patch, wayst, Warp).

Protocol: https://sw.kovidgoyal.net/kitty/graphics-protocol/#control-data-reference
Escape codes are of the form ``<ESC>_G<control data>;<payload><ESC>\\``.
"""

from base64 import b64encode

from kitcat.utils import num_required_lines, reserve_image_rows, send_sequence

CHUNK_SIZE = 4096


def display(img_buf) -> None:
    data = b64encode(img_buf.read()).decode("ascii")
    img_buf.seek(0)

    with reserve_image_rows(num_required_lines(img_buf)):
        send_sequence(_build_escapes(data))


def _build_escapes(data: str) -> str:
    """Chunk base64 PNG data into a sequence of kitty graphics escapes.

    a=T: transmit and display, f=100: PNG payload, m=1: more chunks follow.
    """
    first, more = data[:CHUNK_SIZE], data[CHUNK_SIZE:]
    out = [f"\033_Gm={'1' if more else '0'},a=T,f=100;{first}\033\\"]
    while more:
        chunk, more = more[:CHUNK_SIZE], more[CHUNK_SIZE:]
        out.append(f"\033_Gm={'1' if more else '0'};{chunk}\033\\")
    return "".join(out)
