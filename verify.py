import argparse

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

from build import ROOT, ubuntu_character


def shape(path, text, upem, direction=None):
    font = hb.Font(hb.Face(path.read_bytes()))
    font.scale = (upem, upem)
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    if direction:
        buffer.direction = direction
    hb.shape(font, buffer)
    return [
        (position.x_advance, position.y_advance, position.x_offset, position.y_offset)
        for position in buffer.glyph_positions
    ]


def bounds(font, codepoint):
    glyph_set = font.getGlyphSet()
    glyph_name = font.getBestCmap()[codepoint]
    pen = BoundsPen(glyph_set)
    glyph_set[glyph_name].draw(pen)
    return pen.bounds


def verify(region, glow_weight='Regular'):
    base_region = 'SC' if region == 'Merged' else region
    priority = ['SC', 'TC', 'J'] if region == 'Merged' else list(dict.fromkeys([region, 'SC']))
    variant = '' if glow_weight == 'Regular' else 'MediumCJK'
    destination = ROOT / 'output' / f'GlowUbuntu{region}{variant}-Regular.otf'
    source_paths = {
        key: ROOT / f'GlowSans{key}-Normal-v0.93' / f'GlowSans{key}-Normal-{glow_weight}.otf'
        for key in priority
    }
    source_paths['Ubuntu'] = ROOT / 'ubuntu-font-family-0.83' / 'Ubuntu-R.ttf'
    sources = {key: TTFont(path) for key, path in source_paths.items()}
    maps = {key: font.getBestCmap() for key, font in sources.items()}
    with TTFont(destination) as result:
        upem = result['head'].unitsPerEm
        assert result.sfntVersion == 'OTTO' and 'CFF ' in result
        assert len(result.getGlyphOrder()) < 65536
        assert result['OS/2'].usWeightClass == 400
        family = f'Glow Ubuntu {region}' + (' MediumCJK' if variant else '')
        assert result['name'].getDebugName(1) == family
        assert result['name'].getDebugName(4) == destination.stem
        assert result['name'].getDebugName(6) == destination.stem
        assert result['CFF '].cff.fontNames == [destination.stem]
        assert result['CFF '].cff[0].FamilyName == family
        assert result['CFF '].cff[0].FullName == destination.stem
        expected_codes = set().union(*(set(mapping) for key, mapping in maps.items() if key != 'Ubuntu'))
        expected_codes.update(codepoint for codepoint in maps['Ubuntu'] if ubuntu_character(codepoint))
        assert set(result.getBestCmap()) == expected_codes, (region, 'coverage')
        for text in ['AVATAR To Wa fi ffi', 'Cafe\u0301 A\u0308', '0123456789 - "Hello!"']:
            expected = shape(source_paths['Ubuntu'], text, upem)
            actual = shape(destination, text, upem)
            assert len(actual) == len(expected), (region, text, 'glyph count')
            assert all(abs(left - right) <= 1 for first, second in zip(actual, expected)
                       for left, right in zip(first, second)), (region, text, actual, expected)
        for direction in ['ltr', 'ttb']:
            text = '\u4e2d\u6587\u3001\u65e5\u672c\u8a9e\u3002\u201c\u201d'
            assert shape(destination, text, upem, direction) == shape(
                source_paths[base_region], text, upem, direction
            ), (region, direction, 'CJK shaping')
        for codepoint in result.getBestCmap():
            source = ('Ubuntu' if codepoint in maps['Ubuntu'] and ubuntu_character(codepoint)
                      else next(key for key in priority if codepoint in maps[key]))
            original_bounds = bounds(sources[source], codepoint)
            actual_bounds = bounds(result, codepoint)
            assert (actual_bounds is None) == (original_bounds is None), (region, codepoint)
            if actual_bounds is not None:
                factor = upem / sources[source]['head'].unitsPerEm
                assert all(abs(actual - original * factor) <= 2
                           for actual, original in zip(actual_bounds, original_bounds)), (
                               region, f'U+{codepoint:04X}', source, actual_bounds, original_bounds
                           )
    for font in sources.values():
        font.close()
    print(f'{region}: coverage, outline bounds, Latin shaping, CJK horizontal/vertical shaping OK')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--glow-weight', choices=['Regular', 'Medium'], default='Regular')
    args = parser.parse_args()
    for region in ['SC', 'TC', 'J', 'Merged']:
        verify(region, args.glow_weight)