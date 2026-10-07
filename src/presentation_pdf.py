"""Rebuild the one-page presentation from measured CSV/JSON and real figures.

Uses existing Matplotlib; no additional PDF-authoring dependency is required.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', default='report/REPORT.md')
    parser.add_argument('--csv', default='results/yaw_perturb_sweep.csv')
    parser.add_argument('--failure', default='results/failure_case.json')
    parser.add_argument('--figure-dir', default='results/figures')
    parser.add_argument('--out', help='Default: report/D06_<MSSV>_A.pdf, derived from report metadata')
    args = parser.parse_args()
    text = Path(args.report).read_text()
    mssv = re.search(r'\*\*MSSV:\*\*\s*([A-Za-z0-9]+)', text)
    if not mssv:
        raise ValueError('No verified MSSV in report')
    student = re.search(r'\*\*Họ tên:\*\*\s*(.+)', text).group(1).split(' (')[0]
    rows = list(csv.DictReader(open(args.csv)))
    one = next(r for r in rows if float(r['yaw_deg']) == 1)
    last = max(rows, key=lambda r: float(r['yaw_deg']))
    supported = all(float(r['relative_drop_pct']) >= 10 for r in rows if float(r['yaw_deg']) >= 1)
    failure = json.loads(Path(args.failure).read_text())
    figures = Path(args.figure_dir)
    output = Path(args.out) if args.out else Path(f'report/D06_{mssv.group(1)}_A.pdf')
    output.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(11.69, 8.27), facecolor='#f5f7fb')
    navy, teal = '#152b46', '#007e87'

    def label(x, y, value, size=11, color=navy, weight='normal'):
        fig.text(x, y, value, fontsize=size, color=color, fontweight=weight, va='top')

    def image(path, position, crop=False):
        pixels = plt.imread(path)
        if crop:
            pixels = pixels[int(len(pixels)*.435):]
        ax = fig.add_axes(position)
        ax.imshow(pixels); ax.set_axis_off()

    label(.045, .96, 'LiDAR-camera calibration drift', 24, weight='bold')
    label(.045, .915, f'Day 6 / Topic A  |  {student}  |  {mssv.group(1)}', 10)
    fig.add_artist(FancyBboxPatch((.04, .795), .92, .085, boxstyle='round,pad=0.008',
                                 transform=fig.transFigure, facecolor=navy, edgecolor='none'))
    verdict = 'SUPPORTED' if supported else 'REJECTED'
    label(.055, .866, f'CLAIM {verdict}: tested yaw errors >=1° cause >=10% relative retention loss.', 13, 'white', 'bold')
    label(.055, .834, f"At 1°: {float(one['relative_drop_pct']):.2f}% loss; mean retention {100*float(one['mean_box_retention']):.2f}% (baseline 100%).", 12, 'white')
    label(.045, .765, '01 / Controlled evidence', 13, teal, 'bold')
    image(figures/'yaw_vs_box_retention.png', [.04, .415, .50, .325])
    label(.57, .74, 'FROZEN METHOD', 11, teal, 'bold')
    label(.57, .712, '5 KITTI frames / 16 objects / ≥5 baseline points\n000001, 000004, 000007, 000008, 000009\nCar / Pedestrian / Cyclist; seed 42; no sampling\nOnly yaw changes: 0°, 0.5°, 1°, 2°, 3°\nSame point indices; equal weight per object', 10.5)
    label(.57, .594, 'OTHER MEASUREMENTS', 11, teal, 'bold')
    label(.57, .564, f"At {float(last['yaw_deg']):g}°: mean retention {100*float(last['mean_box_retention']):.2f}%\nPixel shift: median {float(last['median_pixel_shift_px']):.2f} / p95 {float(last['p95_pixel_shift_px']):.2f} px\nFOV stays near {100*float(one['mean_fov_ratio']):.1f}%: weak drift signal\nThree CSVs reproduced byte-for-byte in two runs", 11)
    label(.57, .46, 'Scope: 2D box association can include background.\nFive frames do not establish a universal safety threshold.', 9)
    label(.045, .405, '02 / Real baseline projection', 13, teal, 'bold')
    image(figures/'overlay_000011_r0.0_p0.0_y0.0_t0.0_0.0_0.0.png', [.045, .20, .445, .18])
    label(.045, .195, 'KITTI 000011: returns overlay people, vehicles and road.\nGeometry sanity: (10,0,0) → depth 9.727 m, pixel (613.964,175.007).', 9)
    label(.535, .405, '03 / Geometry failure', 13, teal, 'bold')
    image(Path(failure['figure']), [.535, .195, .425, .18], crop=True)
    label(.535, .188, f"Frame {failure['frame_id']}, {failure['object_class']} #{failure['object_index']}, yaw +{float(failure['yaw_deg']):g}°:\n{failure['retained_points']}/{failure['baseline_points']} retained; median shift {float(failure['median_pixel_shift_px']):.2f} px. Same points move outside GT box.", 9)
    label(.045, .125, '04 / Deployment: ADAS fusion', 12, teal, 'bold')
    label(.045, .096, 'Monitor persistent alignment residuals and sensor timing; log calibration version, FOV and point counts.\nInspect mounts and recalibrate after drift; reduce fusion confidence until alignment is validated.', 10.5)
    label(.045, .035, 'Sources: KITTI Vision Benchmark Suite / results/yaw_perturb_sweep.csv. AI: Codex; verified with geometry, repeat runs and figures.', 8)
    fig.savefig(output, format='pdf', metadata={'Title':'Day 6 - LiDAR-camera calibration QA', 'Author':student,
                                               'CreationDate':None, 'ModDate':None})
    plt.close(fig)
    print(output)


if __name__ == '__main__':
    main()
