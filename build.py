import argparse
import json
import tempfile
import unicodedata
from pathlib import Path

from fontTools import subset
from fontTools.fontBuilder import FontBuilder
from fontTools.merge import Merger
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.scaleUpem import scale_upem


ROOT = Path(__file__).resolve().parent


def ubuntu_character(codepoint):
    character = chr(codepoint)
    return (
        0x20 <= codepoint <= 0x7E
        or 'LATIN' in unicodedata.name(character, '')
        or unicodedata.category(character) == 'Nd'
        or 0x300 <= codepoint <= 0x36F
        or 0xFF61 <= codepoint <= 0xFFDC
        or 0xFFE8 <= codepoint <= 0xFFEE
    )


def normalize(font, codepoints, upem, name):
    options = subset.Options()
    options.layout_features = ['*']
    options.notdef_outline = True
    options.recommended_glyphs = True
    worker = subset.Subsetter(options=options)
    worker.populate(unicodes=codepoints)
    worker.subset(font)
    if font['head'].unitsPerEm != upem:
        scale_upem(font, upem)
    glyph_set = font.getGlyphSet()
    charstrings = {}
    for glyph_name in font.getGlyphOrder():
        width = font['hmtx'][glyph_name][0]
        pen = T2CharStringPen(width, glyph_set)
        glyph_set[glyph_name].draw(pen)
        charstrings[glyph_name] = pen.getCharString()
    for tag in ('CFF ', 'glyf', 'loca', 'cvt ', 'fpgm', 'prep', 'gasp', 'DSIG'):
        if tag in font:
            del font[tag]
    font.sfntVersion = 'OTTO'
    builder = FontBuilder(font=font, isTTF=False)
    builder.setupCFF(name, {'FullName': name, 'FamilyName': name, 'Weight': 'Regular'}, charstrings, {})
    builder.setupMaxp()
    if 'vmtx' not in font:
        builder.setupVerticalMetrics({glyph_name: (upem, 0) for glyph_name in font.getGlyphOrder()})
        builder.setupVerticalHeader(ascent=upem // 2, descent=-(upem // 2))
    return font


def build(region, sources, output, glow_weight='Regular'):
    fonts = {key: TTFont(path) for key, path in sources.items()}
    maps = {key: font.getBestCmap() for key, font in fonts.items()}
    ubuntu_codes = {codepoint for codepoint in maps['Ubuntu'] if ubuntu_character(codepoint)}
    regional_codes = set(maps[region]) - ubuntu_codes
    fallback_codes = set(maps['SC']) - regional_codes - ubuntu_codes
    assignments = [('Ubuntu', ubuntu_codes), (region, regional_codes)]
    if fallback_codes:
        assignments.append(('SC', fallback_codes))
    upem = fonts[region]['head'].unitsPerEm
    variant = '' if glow_weight == 'Regular' else ' MediumCJK'
    family = f'Local Fusion {region}{variant}'
    postscript = f'LocalFusion{region}{variant.replace(" ", "")}-Regular'
    with tempfile.TemporaryDirectory() as temporary:
        paths = []
        vertical_origins = []
        for index, (source, codepoints) in enumerate(assignments):
            path = Path(temporary) / f'{index}.otf'
            normalized = normalize(TTFont(sources[source]), codepoints, upem, f'Part{index}')
            origin_table = normalized.get('VORG')
            vertical_origins.extend(
                origin_table.VOriginRecords.get(glyph_name, origin_table.defaultVertOriginY)
                if origin_table else upem * 0.88
                for glyph_name in normalized.getGlyphOrder()
            )
            normalized.save(path)
            paths.append(str(path))
        merged = Merger().merge(paths)
        if len(vertical_origins) != len(merged.getGlyphOrder()):
            raise RuntimeError('Merged glyph order differs from input order')
        origin_table = newTable('VORG')
        origin_table.majorVersion = 1
        origin_table.minorVersion = 0
        origin_table.defaultVertOriginY = round(upem * 0.88)
        origin_table.VOriginRecords = {
            glyph_name: round(origin)
            for glyph_name, origin in zip(merged.getGlyphOrder(), vertical_origins)
            if round(origin) != origin_table.defaultVertOriginY
        }
        merged['VORG'] = origin_table
        names = merged['name']
        names.names = []
        for name_id, value in {
            1: family, 2: 'Regular', 3: f'{postscript};1.000',
            4: f'{family} Regular', 5: 'Version 1.000', 6: postscript,
            16: family, 17: 'Regular',
            0: 'Glow Sans: Copyright (c) 2020 Celestial Phineas. Ubuntu: see source copyright.txt.',
            13: 'Private local build combining OFL-1.1 and Ubuntu Font Licence inputs. Not licensed for redistribution.',
        }.items():
            names.setName(value, name_id, 3, 1, 0x409)
        top = merged['CFF '].cff[0]
        merged['CFF '].cff.fontNames = [postscript]
        top.FamilyName = family
        top.FullName = f'{family} Regular'
        top.Weight = 'Regular'
        for tag in ('hhea', 'OS/2'):
            original = fonts[region][tag]
            target = merged[tag]
            fields = ('ascent', 'descent', 'lineGap') if tag == 'hhea' else (
                'sTypoAscender', 'sTypoDescender', 'sTypoLineGap', 'usWinAscent', 'usWinDescent'
            )
            for field in fields:
                setattr(target, field, getattr(original, field))
        merged['OS/2'].usWeightClass = 400
        destination = output / f'{postscript}.otf'
        merged.save(destination)
    with TTFont(destination) as result:
        result.ensureDecompiled()
        result_map = result.getBestCmap()
        expected = ubuntu_codes | regional_codes | fallback_codes
        if set(result_map) != expected:
            raise RuntimeError(f'{region}: output character coverage differs from inputs')
        for source, codepoints in assignments:
            source_font = fonts[source]
            factor = upem / source_font['head'].unitsPerEm
            for codepoint in codepoints:
                expected_width = round(source_font['hmtx'][maps[source][codepoint]][0] * factor)
                if result['hmtx'][result_map[codepoint]][0] != expected_width:
                    raise RuntimeError(f'{region}: wrong advance width at U+{codepoint:04X}')
    report = {
        'region': region, 'file': destination.name, 'characters': len(expected),
        'sources': {source: len(codes) for source, codes in assignments},
        'upem': upem,
        'glow_weight': glow_weight, 'ubuntu_weight': 'Regular',
    }
    print(json.dumps(report))
    for font in fonts.values():
        font.close()
    return report


def main():
    parser = argparse.ArgumentParser(description='Build private Regular CFF OTF fonts with Ubuntu Latin glyphs.')
    parser.add_argument('--region', nargs='+', choices=['SC', 'TC', 'J'], default=['SC', 'TC', 'J'])
    parser.add_argument('--source-dir', type=Path, default=ROOT)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'output')
    parser.add_argument('--glow-weight', choices=['Regular', 'Medium'], default='Regular')
    args = parser.parse_args()
    sources = {
        region: args.source_dir / f'GlowSans{region}-Normal-v0.93' / f'GlowSans{region}-Normal-{args.glow_weight}.otf'
        for region in {'SC', *args.region}
    }
    sources['Ubuntu'] = args.source_dir / 'ubuntu-font-family-0.83' / 'Ubuntu-R.ttf'
    for path in sources.values():
        if not path.is_file():
            parser.error(f'Missing source font: {path}')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reports = [build(region, sources, args.output_dir, args.glow_weight) for region in args.region]
    report_name = 'build-report.json' if args.glow_weight == 'Regular' else 'build-report-MediumCJK.json'
    (args.output_dir / report_name).write_text(json.dumps(reports, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()