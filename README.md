# kitcat

This project introduces a new `kitcat` backend for Matplotlib that allows plots to be displayed directly in the terminal. It utilizes the "agg" backend for rendering plots before sending them to the terminal.

- Direct Matplotlib plotting in terminal emulators that support [Kitty](https://sw.kovidgoyal.net/kitty/graphics-protocol/) or [iTerm2](https://iterm2.com/documentation-images.html) graphics protocols.
- Works seamlessly over SSH and inside tmux.

<p float="left">
  <img src="https://raw.githubusercontent.com/mil-ad/kitcat/main/demo1.gif" width="45%" />
  <img src="https://raw.githubusercontent.com/mil-ad/kitcat/main/demo2.gif" width="45%" />
</p>

## Installation

```
pip install kitcat
```

## Usage

Select `kitcat` backend after importing matplotlib:

```py
import matplotlib
matplotlib.use("kitcat")
```

or if pyplot is already imported, `switch_backend()` can be used to select kitcat backend:

```py
import matplotlib.pyplot as plt
plt.switch_backend("module://kitcat")
```

## Terminal Emulator Support

[Kitty](https://sw.kovidgoyal.net/kitty/) and [Ghostty](https://ghostty.org/) are the recommended terminals. They implement [modern protocol][placeholders] which let kitcat embed the image into the terminal's text buffer rather than overlaying it on the screen. This means plots scroll with the buffer, clip correctly at pane boundaries, and behave properly inside tmux — see [tmux notes](#tmux-notes). Other supported terminals still work, but the image is drawn at a fixed screen position and won't track the buffer as cleanly.

| Terminal Emulator    | Supported | Notes                                                   |
| -------------------- | --------- | ------------------------------------------------------- |
| Kitty                | ✅✨      |                                                         |
| Ghostty              | ✅✨      |                                                         |
| iTerm2               | ✅        |                                                         |
| VSCode               | ✅        | Requires `terminal.integrated.enableImages` in settings |
| WezTerm              | ✅        |                                                         |
| tmux                 | ✅        | See [tmux notes](#tmux-notes)                           |
| Warp                 | ✅        |                                                         |
| wayst                | ✅        |                                                         |
| st                   | ✅        | Requires `st-kitty-graphics` [patch][st-patch]          |
| Zellij               | ❌        |                                                         |
| Alacritty            | ❌        |                                                         |
| Terminal.app (macOS) | ❌        |                                                         |

### tmux notes

On **Kitty** and **Ghostty**, kitcat uses [Unicode placeholders][placeholders] so the image becomes part of tmux's text buffer — it scrolls with the buffer, clips at the pane boundary, and disappears when the pane is hidden. On other terminals, the image is drawn directly by the outer emulator and stays at a fixed screen position (so it can persist when switching panes — this is a tmux/terminal limitation, not a kitcat one).

Either way, `set -g allow-passthrough on` is required in your tmux config.

## Acknowledgements

I discovered [matplotlib-backend-kitty](https://github.com/jktr/matplotlib-backend-kitty) repository, which provides similar functionality in Kitty. I aimed to create a simpler solution that works across any terminal supporting the protocol.

[st-patch]: https://st.suckless.org/patches/kitty-graphics-protocol/
[placeholders]: https://sw.kovidgoyal.net/kitty/graphics-protocol/#unicode-placeholders
