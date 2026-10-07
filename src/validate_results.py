"""Verify analytic geometry fixtures and the benchmark's frozen-cohort CSVs."""
from pathlib import Path
import csv
import sys

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from starter.datasets import load_frame
from starter.projection import cam_to_image, perturb_extrinsic, velo_to_cam


def main():
    frame = load_frame('data/synthetic', '000000')
    point = np.array([[10., 0., 0.]])
    cam = velo_to_cam(point, frame['calib'])
    uv, depth, mask = cam_to_image(cam, frame['calib'].P2, frame['image'].shape)
    np.testing.assert_allclose(depth, [9.72732109], atol=1e-6)
    np.testing.assert_allclose(uv, [[613.96414869, 175.00653723]], atol=1e-6)
    assert mask.tolist() == [True]
    # Independent yaw construction checks helper axis, direction, composition and no mutation.
    original = frame['calib'].Tr_velo_to_cam.copy()
    angle = np.deg2rad(1.)
    rotated = np.array([[10*np.cos(angle), 10*np.sin(angle), 0.]])
    actual = velo_to_cam(point, perturb_extrinsic(frame['calib'], yaw_deg=1))
    np.testing.assert_allclose(actual, velo_to_cam(rotated, frame['calib']), atol=1e-12)
    np.testing.assert_array_equal(original, frame['calib'].Tr_velo_to_cam)
    shifted, _, _ = cam_to_image(actual, frame['calib'].P2, frame['image'].shape)
    assert shifted[0, 0] < uv[0, 0]
    # Hand-solvable pinhole with focal length 100, principal point (50,50).
    P = np.array([[100., 0., 50., 0.], [0., 100., 50., 0.], [0., 0., 1., 0.]])
    points = np.array([[1,2,10], [0,0,-1], [np.nan,0,1], [np.inf,0,1],
                       [0,0,.1], [-5,0,10], [5,0,10], [0,0,10]])
    pixels, depths, valid = cam_to_image(points, P, (100,100,3))
    np.testing.assert_allclose(pixels, [[60,70], [0,50], [50,50]])
    np.testing.assert_allclose(depths, [10,10,10])
    assert valid.tolist() == [True,False,False,False,False,True,False,True]
    assert velo_to_cam(np.empty((0,3)), frame['calib']).shape == (0,3)
    assert cam_to_image(np.empty((0,3)), P, (100,100))[0].shape == (0,2)
    for denominator in (0., 1e-14, np.nan, np.inf):
        Q=P.copy(); Q[2]=[0,0,0,denominator]
        assert not cam_to_image(np.array([[0.,0.,10.]]), Q, (100,100))[2].any()
    invalid = velo_to_cam(np.array([[np.nan,0,0]]), frame['calib'])
    assert np.isnan(invalid).all()
    print('PASS: analytic geometry, point order, yaw convention, NaN/Inf, empty input, image/depth boundaries')
    with open('results/yaw_perturb_sweep.csv') as f:
        summary=list(csv.DictReader(f))
    with open('results/yaw_perturb_sweep_details.csv') as f:
        details=list(csv.DictReader(f))
    cohorts=[]
    for level in summary:
        objects=[r for r in details if float(r['yaw_deg']) == float(level['yaw_deg'])]
        cohort={(r['frame_id'],r['object_index'],r['object_class'],r['baseline_points']) for r in objects}
        assert len(objects)==len(cohort)==int(level['num_objects'])==16
        assert len({r['frame_id'] for r in objects})==int(level['num_frames'])==5
        cohorts.append(cohort)
        ratios=[]
        for obj in objects:
            n=int(obj['baseline_points']); kept=int(obj['retained_points'])
            assert n >= 5 and 0 <= kept <= n
            assert float(obj['retention']) == kept/n
            ratios.append(kept/n)
        np.testing.assert_allclose(float(level['mean_box_retention']), np.mean(ratios), atol=1e-14)
        np.testing.assert_allclose(float(level['median_box_retention']), np.median(ratios), atol=1e-14)
        np.testing.assert_allclose(float(level['relative_drop_pct']),100*(1-np.mean(ratios)),atol=1e-12)
        assert 0 <= float(level['mean_fov_ratio']) <= 1
        assert 0 <= float(level['median_pixel_shift_px']) <= float(level['p95_pixel_shift_px'])
    assert all(c == cohorts[0] for c in cohorts)
    assert {float(r['yaw_deg']) for r in summary} == {0,.5,1,2,3}
    print('PASS: frozen frames/classes/objects/counts; retention aggregates independently checked from integer counts')


if __name__ == '__main__':
    main()
