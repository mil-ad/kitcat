"""iTerm2 inline images protocol (OSC 1337).

Used for iTerm.app and VSCode's integrated terminal — both implement the
iTerm2 protocol and do not implement kitty graphics.

Reference: https://iterm2.com/documentation-images.html
"""

from base64 import b64encode

from kitcat.utils import num_required_lines, reserve_image_rows, send_sequence


def display(img_buf) -> None:
    pixel_data = img_buf.read()
    img_buf.seek(0)
    data = b64encode(pixel_data).decode("ascii")

    # `size` is optional in iTerm2 but required by VSCode's terminal.
    payload = f"\033]1337;File=inline=1;size={len(pixel_data)}:{data}\a"

    with reserve_image_rows(num_required_lines(img_buf)):
        send_sequence(payload)
