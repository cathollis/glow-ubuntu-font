# Glow Ubuntu Fonts

Build four private Regular CFF OpenType fonts from Glow Sans Normal v0.93
and Ubuntu 0.83. Only the scripts and documentation are intended for publication.
Source fonts and generated fonts are excluded by `.gitignore`.

## Setup

```powershell
conda env create -f environment.yml
conda activate glow-ubuntu-font
```

If the environment already exists, activate it and run `python -m pip install -r requirements.txt`.

Place these files beside `build.py`, preserving their directory names:

```text
GlowSansSC-Normal-v0.93/GlowSansSC-Normal-Regular.otf
GlowSansTC-Normal-v0.93/GlowSansTC-Normal-Regular.otf
GlowSansJ-Normal-v0.93/GlowSansJ-Normal-Regular.otf
ubuntu-font-family-0.83/Ubuntu-R.ttf
```

Obtain Glow Sans from https://github.com/welai/glow-sans and Ubuntu from
https://design.ubuntu.com/font. Keep the original copyright and licence files
with your local source copies. FontLab VFB sources are not used.

## Build And Verify

```powershell
python build.py
python verify.py
```

Outputs are `output/GlowUbuntuSC-Regular.otf`, `GlowUbuntuTC-Regular.otf`,
`GlowUbuntuJ-Regular.otf`, and `GlowUbuntuMerged-Regular.otf`, plus `output/build-report.json`.
Use `python build.py --region SC` to build just SC. `--source-dir` and
`--output-dir` accept alternative directories. The verification command checks
all four outputs in the default output directory. The Merged output keeps SC
glyphs and adds characters missing from SC, first from TC and then from J.
Ubuntu overrides the same character sets in all four outputs. Shared characters
keep SC glyphs; the merged output does not add automatic regional variants.
Use `python build.py --region Merged` to build only this combined font.

## Local Preview

For slightly heavier CJK glyphs while keeping Ubuntu Regular unchanged:

```powershell
python build.py --glow-weight Medium
python verify.py --glow-weight Medium
```

This uses Glow Sans Normal Medium for both regional glyphs and SC fallback.
Outputs are `output/GlowUbuntu{SC,TC,J,Merged}MediumCJK-Regular.otf` with separate
family names, so they can coexist with the original builds. The font style
remains Regular (400) for normal text; only the Glow source weight changes.
The preview defaults to this variant and offers a Regular/Medium selector.
Both variants discard source hinting as described below.

Open `preview.html` directly in a browser after building the fonts. It loads
the local output and source fonts without external dependencies. The page
compares the merged font with the regional Glow Sans and Ubuntu originals,
with editable text, region selection, font size, line height and vertical layout.
Each font has a loading status; a failure indicates a missing file or a browser
restriction on local font loading. Do not publish or serve these fonts publicly.

## Character Selection

Each output uses its corresponding Glow Sans region first. Characters absent
from that regional font fall back to SC. This produces separate regional fonts:
one Unicode character cannot simultaneously select its SC, TC and J glyph in
an ordinary character map.

Ubuntu overrides characters it actually contains in the following sets:

- ASCII U+0020-U+007E: Latin letters, digits, space and halfwidth punctuation.
- Unicode characters whose name includes LATIN.
- Unicode decimal digits (category Nd).
- Combining Diacritical Marks U+0300-U+036F, to support accented Latin text.
- Halfwidth forms U+FF61-U+FFDC and U+FFE8-U+FFEE, if present in Ubuntu.

Other characters remain Glow Sans, including curly quotes U+2018-U+201F,
em dash U+2014, ellipsis U+2026, Chinese punctuation and fullwidth forms.
ASCII `-` and straight quotes use Ubuntu. Missing Ubuntu characters retain
the regional/SC fallback. The rules live in `ubuntu_character` in `build.py`.

Ubuntu is scaled to the regional font's units per em without an extra visual
size adjustment. Regional line metrics are retained. Layout tables are subsetted
and merged, including ligatures, kerning, combining marks and CJK vertical
substitutions. Outlines are rebuilt as non-CID CFF cubic curves for compatibility
with the merger. Original CFF and TrueType hinting is not retained. This is not
a variable font. Inspect the visual balance and small-size rendering before use.

The build checks coverage and advance widths for every mapped character. The
verification command also compares outline bounds for every mapped character
and uses HarfBuzz to compare representative Latin and CJK shaping with the sources.
It is not a complete visual or OpenType conformance audit.

## Licensing

Glow Sans font data is under SIL OFL-1.1; see `glow-sans-ofl.txt`. Ubuntu 0.83
is under the Ubuntu Font Licence 1.0; see the original package's `LICENCE.txt`
and https://canonical.com/legal/font-licence. Both require derivatives to remain
under their respective licences, so this project does not offer a redistribution
licence for the combined fonts. Build only for private local use; do not publish
the generated fonts or include them in releases, packages, websites or applications.
Keeping both licence texts does not resolve the redistribution conflict.

The independently written scripts and documentation in this repository are
provided under MIT (see `LICENSE`). That licence does not apply to any source
font, upstream licence text or generated font. This directory is not automatically
published to GitHub by the build scripts.