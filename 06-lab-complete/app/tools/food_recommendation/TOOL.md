---
name: filter_and_recommend_food
track: core
kind: local_function
provider: Internal Dataset
requires_env: []
inputs: [loai_mon, vi, di_ung, ban_kinh_km, ngan_sach]
outputs: [items, applied_filters, total_matches_found, items_returned]
side_effect: false
---
# filter_and_recommend_food

Tìm kiếm, lọc và chấm điểm các món ăn từ dataset nội bộ dựa trên nhu cầu của người dùng. 
Hệ thống sẽ áp dụng các bộ lọc bắt buộc (hard filters) bao gồm khoảng cách tối đa, ngân sách và thành phần dị ứng, sau đó so khớp (soft match) theo loại món và hương vị để trả về top 3 gợi ý phù hợp nhất.