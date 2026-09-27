"""Freeze a GitHub Readme Stats card in its final, fully drawn state.

The card hides its text and rank until CSS animations run, so tools that do not
run SVG animations (crawlers, screenshots, frozen tabs) see a blank card. This
drops the animations and writes their end state as static styles. Safe to run
more than once. Usage: python3 profile/freeze_svg.py profile/stats-*.svg
"""
import pathlib
import re
import sys


def freeze(svg):
    ring = re.search(r"@keyframes rankAnimation\s*\{.*?to\s*\{\s*stroke-dashoffset:\s*([\d.]+);", svg, re.S)
    svg = re.sub(r"\s*animation:[^;]*;", "", svg)
    svg = re.sub(r"(\.stagger\s*\{[^}]*?)opacity:\s*0;", r"\1opacity: 1;", svg)
    svg = re.sub(r"(\.rank-text\s*\{)", r"\1 transform: translate(-5px, 5px);", svg, count=1) \
        if "translate(-5px, 5px);" not in re.search(r"\.rank-text\s*\{[^}]*\}", svg).group(0) else svg
    if ring:
        svg = re.sub(r"(\.rank-circle\s*\{)", rf"\1 stroke-dashoffset: {ring.group(1)};", svg, count=1)
        svg = re.sub(r"@keyframes rankAnimation\s*\{.*?\}\s*\}", "", svg, count=1, flags=re.S)
    return svg


for path in map(pathlib.Path, sys.argv[1:]):
    if path.is_file():
        path.write_text(freeze(path.read_text(encoding="utf-8")), encoding="utf-8")
