"""Controlled yaw experiment. Authored with Codex; uses repository loaders/helpers.

Box association is a 2D proxy, not proof of physical object membership.
Point indices and qualifying objects are frozen once at baseline.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from starter.datasets import load_frame
from starter.projection import cam_to_image, perturb_extrinsic, velo_to_cam

CLASSES = ('Car', 'Pedestrian', 'Cyclist')


def project_all(frame, calib):
    """Full-index pixels, geometric validity, FOV mask, and finite-front mask.

    Full-index pixels include out-of-FOV projections for failure visualization.
    The main displacement metric uses points in FOV at both projections.
    """
    cam = velo_to_cam(frame['points'][:, :3], calib)
    front = np.isfinite(cam).all(1) & (cam[:, 2] > .1)
    q = np.full((len(cam), 3), np.nan)
    q[front] = np.c_[cam[front], np.ones(front.sum())] @ calib.P2.T
    valid = front & np.isfinite(q).all(1) & (np.abs(q[:, 2]) > 1e-12)
    uv = np.full((len(cam), 2), np.nan)
    uv[valid] = q[valid, :2] / q[valid, 2:3]
    valid &= np.isfinite(uv).all(1)
    _, _, fov = cam_to_image(cam, calib.P2, frame['image'].shape)
    return uv, valid, fov, front


def in_box(uv, box):
    x1, y1, x2, y2 = box
    return (np.isfinite(uv).all(1) & (uv[:, 0] >= x1) & (uv[:, 0] <= x2)
            & (uv[:, 1] >= y1) & (uv[:, 1] <= y2))


def baseline_objects(frame, uv, fov, minimum):
    objects = []
    for index, obj in enumerate(frame['labels']):
        if obj.type not in CLASSES:
            continue
        indices = np.flatnonzero(fov & in_box(uv, obj.bbox))
        if len(indices) >= minimum:
            objects.append((index, obj, indices))
    return objects


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(args):
    np.random.seed(args.seed)  # No random sampling is used.
    frames = []
    for fid in args.frames:
        frame = load_frame(args.data_root, fid)
        uv, valid, fov, _ = project_all(frame, frame['calib'])
        objects = baseline_objects(frame, uv, fov, args.min_baseline_points)
        if not objects:
            raise ValueError(f'{fid}: no qualifying baseline objects')
        frames.append((fid, frame, uv, fov, objects))
    summary, details, frame_rows = [], [], []
    for yaw in args.yaw_deg:
        retentions, fov_ratios, shifts = [], [], []
        for fid, frame, baseline_uv, baseline_valid, objects in frames:
            calib = perturb_extrinsic(frame['calib'], yaw_deg=yaw)
            uv, valid, fov, front = project_all(frame, calib)
            ratio = float(fov.sum() / front.sum()) if front.any() else 0.
            fov_ratios.append(ratio)
            common = baseline_valid & fov
            displacement = np.linalg.norm(uv[common] - baseline_uv[common], axis=1)
            shifts.append(displacement)
            frame_rows.append(dict(yaw_deg=yaw, frame_id=fid, num_points=len(uv),
                                   finite_front_points=int(front.sum()), fov_points=int(fov.sum()),
                                   fov_ratio=ratio, common_fov_points=int(common.sum())))
            for index, obj, indices in objects:
                retained = int((fov[indices] & in_box(uv[indices], obj.bbox)).sum())
                retention = retained / len(indices)
                retentions.append(retention)
                point_shift = np.linalg.norm(uv[indices] - baseline_uv[indices], axis=1)
                point_shift = point_shift[valid[indices]]
                details.append(dict(yaw_deg=yaw, frame_id=fid, object_index=index,
                                    object_class=obj.type, baseline_points=len(indices),
                                    retained_points=retained, retention=retention,
                                    camera_depth_m=float(obj.location[2]),
                                    median_pixel_shift_px=float(np.median(point_shift)) if len(point_shift) else '',
                                    seed=args.seed))
        displacement = np.concatenate(shifts)
        mean = float(np.mean(retentions))
        summary.append(dict(yaw_deg=yaw, num_frames=len(frames), num_objects=len(retentions),
                            mean_fov_ratio=float(np.mean(fov_ratios)), mean_box_retention=mean,
                            median_box_retention=float(np.median(retentions)),
                            relative_drop_pct=100 * (1 - mean),
                            median_pixel_shift_px=float(np.median(displacement)),
                            p95_pixel_shift_px=float(np.percentile(displacement, 95)),
                            common_fov_points=len(displacement),
                            min_baseline_points=args.min_baseline_points, seed=args.seed))
    baseline = next(row for row in summary if row['yaw_deg'] == 0)
    if baseline['mean_box_retention'] != 1:
        raise AssertionError('Baseline retention must be one')
    output = Path(args.output_csv)
    write_csv(output, summary)
    write_csv(output.with_name(output.stem + '_details.csv'), details)
    write_csv(output.with_name(output.stem + '_frames.csv'), frame_rows)
    figure_dir = Path(args.figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)
    levels = [r['yaw_deg'] for r in summary]
    fig, ax = plt.subplots(figsize=(7, 4.2), layout='constrained')
    ax.plot(levels, [100*r['mean_box_retention'] for r in summary], 'o-', label='Object mean')
    ax.plot(levels, [100*r['median_box_retention'] for r in summary], 's--', label='Object median')
    ax.axhline(90, color='#a33', linestyle=':', label='10% drop threshold')
    ax.set(xlabel='LiDAR-frame yaw error (degrees)', ylabel='Baseline-associated point retention (%)',
           title=f'KITTI: {len(frames)} frozen frames, {baseline["num_objects"]} objects', ylim=(0, 105), xticks=levels)
    ax.grid(alpha=.25); ax.legend()
    fig.savefig(figure_dir/'yaw_vs_box_retention.png', dpi=180); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4.2), layout='constrained')
    ax.plot(levels, [r['median_pixel_shift_px'] for r in summary], 'o-', label='Median')
    ax.plot(levels, [r['p95_pixel_shift_px'] for r in summary], 's--', label='95th percentile')
    ax.set(xlabel='LiDAR-frame yaw error (degrees)', ylabel='Pixel displacement (px)',
           title='Same points in image FOV at baseline and perturbed yaw', xticks=levels, ylim=(0, None))
    ax.grid(alpha=.25); ax.legend()
    fig.savefig(figure_dir/'yaw_vs_pixel_shift.png', dpi=180); plt.close(fig)
    for row in summary:
        print(f"yaw={row['yaw_deg']:g}: retention={row['mean_box_retention']:.6f}, "
              f"drop={row['relative_drop_pct']:.3f}%, median shift={row['median_pixel_shift_px']:.3f}px")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--data-root', default='data/kitti_mini')
    parser.add_argument('--frames', nargs='+', required=True, help='Frozen frame IDs, same at every yaw level')
    parser.add_argument('--yaw-deg', nargs='+', type=float, default=[0, .5, 1, 2, 3], help='Absolute offsets from original calibration; must include 0')
    parser.add_argument('--seed', type=int, default=42, help='Recorded seed; experiment uses every point, no sampling')
    parser.add_argument('--min-baseline-points', type=int, default=5)
    parser.add_argument('--output-csv', default='results/yaw_perturb_sweep.csv')
    parser.add_argument('--figure-dir', default='results/figures')
    args = parser.parse_args()
    if len(set(args.frames)) != len(args.frames):
        parser.error('Frame IDs must be unique')
    if (0 not in args.yaw_deg or len(set(args.yaw_deg)) != len(args.yaw_deg)
            or not np.isfinite(args.yaw_deg).all()):
        parser.error('Yaw levels must be finite, unique, and include 0')
    if args.min_baseline_points < 1:
        parser.error('Minimum baseline points must be positive')
    run(args)


if __name__ == '__main__':
    main()
