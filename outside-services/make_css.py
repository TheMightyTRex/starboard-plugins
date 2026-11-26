#!/usr/bin/env python3
"""Retired: ds.css and font.woff2 are now written by the design system's own sync tool, so every copy is made the same way.

From the design system's folder (github.com/TheMightyTRex/design-system), with PLUGINS_DIR set to this repository:

    PLUGINS_DIR=~/src/starboard-plugins python3 tools/sync.py

It copies tokens.css and components.css into ds.css, and the font, and does the same for tv-station's ds-tokens.css.
"""
import sys

sys.exit(__doc__)
