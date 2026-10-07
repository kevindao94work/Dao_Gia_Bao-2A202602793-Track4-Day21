# Day 6 / Topic A: ghi chú trình bày 3 phút

## 0:00–0:30 / Câu hỏi

Nếu gá LiDAR lệch yaw, camera và LiDAR vẫn chạy nhưng projection còn khớp object không? Giả thuyết chốt ở CP1: yaw ≥1° làm giảm mean retention ≥10% so với baseline. Đây là kiểm tra alignment, không phải benchmark detector.

## 0:30–1:15 / Phương pháp

Dùng 5 frame KITTI đầu tiên theo ID đủ điều kiện: 000001, 000004, 000007, 000008, 000009. Chốt frame trước sweep. Chiếu bằng P2 · R0_rect · Tr; bỏ NaN, depth≤0.1 m và điểm ngoài ảnh. Với mỗi box Car/Pedestrian/Cyclist có ≥5 điểm baseline, giữ nguyên tập chỉ số điểm: có 16 object. Mỗi yaw 0/0.5/1/2/3° bắt đầu từ calibration gốc; roll/pitch/translation không đổi. Retention từng box là tỷ lệ điểm gốc còn trong chính box đó, mean mỗi object có trọng số bằng nhau. Pixel shift median/p95 gộp trên cùng điểm trong FOV ở cả hai projection.

## 1:15–2:00 / Bằng chứng

Mở plot retention và PDF. Mean retention: 100%, 83.39%, 64.35%, 40.66%, 28.53%. Tại 1° giảm 35.65%, nên claim supported trên mọi mức đã thử ≥1°. Tại 3°, shift median 43.58 px và p95 60.69 px. FOV khoảng 31.4% gần như không đổi: đếm điểm trong ảnh không đủ phát hiện calibration drift. Chạy hai lần cả ba CSV giống byte; kiểm tra geometry bằng điểm synthetic (10,0,0) cho depth 9.727 m và pixel (613.964,175.007).

## 2:00–2:30 / Failure

Mở fail_01_yaw_3deg_cyclist.png. Quy tắc lấy retention nhỏ nhất ở yaw lớn nhất, hòa thì lấy nhiều baseline points hơn: frame 000007, Cyclist #3 ở depth 34.09 m. 0/73 điểm còn trong box; shift median 44.21 px. Positive yaw trong hệ LiDAR dịch projection trái trên ảnh, vượt box hẹp: lỗi Geometry. Không đổi sensor input hay label để tạo ảnh.

## 2:30–3:00 / Triển khai

ADAS nên giám sát alignment residual và timestamp; log calibration version, FOV, point count, sensor state. Projection/matching tốn compute; kiểm tra định kỳ/ROI cần xác thực lại độ nhạy. Drift kéo dài thì kiểm tra mount, timing, recalibrate và giảm confidence nhánh fusion. 10% trong bài là ngưỡng hypothesis, không phải ngưỡng an toàn áp dụng ngay.

## Câu hỏi dự kiến

- **Khi nào claim có thể sai?** Scene chỉ có vật lớn/gần, box rộng, sensor/focal length khác, yaw âm, metric dùng point-weighted thay object-weighted, hoặc frame khác. Box 2D có thể chứa nền/đường; 100% baseline là định nghĩa, không phải ground-truth calibration hoàn hảo. Không suy diễn liên tục cho mọi yaw ≥1°.
- **nuScenes có giống không?** Không thể khẳng định. Repo có 32-beam LiDAR, camera/image geometry khác và offset thời gian được adapter bù ego motion; box được dựng từ annotation 3D. Bài chỉ chạy demo adapter, chưa chạy cross-dataset benchmark nên không nêu chênh lệch số học.
- **Online có GT box/baseline không?** Thường không. Cần camera detection/edge hoặc residual độc lập với transform bị kiểm tra, rồi đánh giá monitor trên log đã xác nhận. Offline retention ở đây không tự động trở thành production health score.
- **Giải thích dòng code:** row-vector homogeneous nhân T.T; T=R0_rect@Tr. Helper tạo D rồi Tr@D; mỗi mức deepcopy. Mask giữ nguyên thứ tự điểm; chỉ các hàng hữu hạn/front chia denominator; out-of-FOV ở sweep tính mất retention.
- **Đã tự tập chưa?** Đây là ghi chú do Codex chuẩn bị; học viên cần tự đọc code và tập nói 3 phút, chưa có bằng chứng học viên đã tập.
