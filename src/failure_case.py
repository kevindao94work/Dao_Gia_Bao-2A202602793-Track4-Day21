"""Select the worst retention at largest yaw; ties prefer more baseline points."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

from calibration_qa import baseline_objects, in_box, project_all
from starter.datasets import load_frame
from starter.projection import perturb_extrinsic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', default='data/kitti_mini')
    parser.add_argument('--details-csv', default='results/yaw_perturb_sweep_details.csv')
    parser.add_argument('--out', default='results/figures/fail_01_yaw_3deg_cyclist.png')
    parser.add_argument('--metadata', default='results/failure_case.json')
    args = parser.parse_args()
    with open(args.details_csv, newline='') as file:
        rows = list(csv.DictReader(file))
    maximum = max(float(r['yaw_deg']) for r in rows)
    candidates = [r for r in rows if float(r['yaw_deg']) == maximum]
    selected = min(candidates, key=lambda r: (float(r['retention']), -int(r['baseline_points']),
                                            r['frame_id'], int(r['object_index'])))
    frame = load_frame(args.data_root, selected['frame_id'])
    baseline_uv, _, baseline_fov, _ = project_all(frame, frame['calib'])
    index = int(selected['object_index'])
    _, obj, indices = next(o for o in baseline_objects(frame, baseline_uv, baseline_fov, 1) if o[0] == index)
    yaw = float(selected['yaw_deg'])
    perturbed_uv, valid, fov, _ = project_all(frame, perturb_extrinsic(frame['calib'], yaw_deg=yaw))
    retained = int((fov[indices] & in_box(perturbed_uv[indices], obj.bbox)).sum())
    assert len(indices) == int(selected['baseline_points'])
    assert retained == int(selected['retained_points'])
    x1, y1, x2, y2 = obj.bbox
    figure = plt.figure(figsize=(11, 7), layout='constrained')
    grid = figure.add_gridspec(2, 2, height_ratios=[1, 1.5])
    context = figure.add_subplot(grid[0, :])
    rgb = cv2.cvtColor(frame['image'], cv2.COLOR_BGR2RGB)
    context.imshow(rgb)
    context.add_patch(Rectangle((x1, y1), x2-x1, y2-y1, fill=False, edgecolor='#39ff14', linewidth=2))
    context.set_title(f"Frame {selected['frame_id']} | {obj.type} object #{index} | camera depth {obj.location[2]:.2f} m")
    context.set_axis_off()
    for column, (pixels, title, color) in enumerate([
            (baseline_uv, 'Baseline yaw 0 degrees', '#00e5ff'),
            (perturbed_uv, f'Yaw +{yaw:g} degrees: retained {retained}/{len(indices)} ({100*retained/len(indices):.1f}%)', '#ff5533')]):
        ax = figure.add_subplot(grid[1, column])
        ax.imshow(rgb)
        ax.add_patch(Rectangle((x1, y1), x2-x1, y2-y1, fill=False, edgecolor='#39ff14', linewidth=2, label='Unchanged GT box'))
        usable = indices[np.isfinite(pixels[indices]).all(1)]
        ax.scatter(pixels[usable, 0], pixels[usable, 1], s=14, c=color, label='Same baseline-associated points')
        ax.set_xlim(max(0, x1-70), min(rgb.shape[1], x2+70))
        ax.set_ylim(min(rgb.shape[0], y2+35), max(0, y1-35))
        ax.set(title=title, xlabel='Image u (px)', ylabel='Image v (px)')
        ax.legend(fontsize=8, loc='lower left')
    figure.suptitle(f"Geometry failure: median shift {float(selected['median_pixel_shift_px']):.2f} px\nKITTI Vision Benchmark Suite - deterministic worst-retention selection", fontsize=13)
    output = Path(args.out); output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180); plt.close(figure)
    selected['selection_rule'] = 'Largest tested yaw, lowest retention, then highest baseline count, frame ID, object index.'
    selected['figure'] = args.out
    metadata = Path(args.metadata); metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(json.dumps(selected, indent=2) + '\n')
    print(json.dumps(selected, indent=2))


if __name__ == '__main__':
    main()
