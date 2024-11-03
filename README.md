# kitcat

This project introduces a new `kitcat` backend for Matplotlib that allows plots to be displayed directly in the terminal. It utilizes the "agg" backend for rendering plots before sending them to the terminal.

- Direct Matplotlib plotting in terminal emulators that support [Kitty graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/)
- Works seamlessly over SSH

## Terminal Emulator Support

Not all terminal emulators support Kitty's graphics protocol. I haven't tested this extensively, so please let me know if you find other emulators that are compatible, and I will update the list accordingly.

| Terminal Emulator    | Supported  |
| -------------------- | ---------- |
| Kitty                | ✅         |
| iTerm2               | ✅         |
| WezTerm              | ✅         |
| Alacritty            | ❌         |
| Warp                 | ❌         |
| Terminal.app (macOS) | ❌         |
| wayst                | ✅         |

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

## Acknowledgements

I discovered [matplotlib-backend-kitty](https://github.com/jktr/matplotlib-backend-kitty) repository, which provides similar functionality in Kitty. I aimed to create a simpler solution that works across any terminal supporting the protocol.
