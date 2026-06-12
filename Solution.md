# Solution.md — Delivery Checklist — Day 12

Đây là tổng hợp đáp án cho các Codelab từ Part 1 đến Part 5.

---

## Part 1: Localhost vs Production

**Exercise 1.1: Phát hiện anti-patterns (trong basic `app.py`)**
1. API key bị hardcode trong source code.
2. Không có cơ chế quản lý cấu hình (config management) như đọc từ environment variable.
3. Sử dụng lệnh `print` thay vì structured logging, có nguy cơ in ra log chứa keys bảo mật.
4. Thiếu các endpoint health check (`/health`, `/ready`).
5. Chỉ nhận port tĩnh (cố định 8000) và IP host là `localhost` (127.0.0.1) thay vì public binding `0.0.0.0` (cần cho Docker/Cloud).

**Exercise 1.3: Bảng so sánh Basic vs Advanced**

| Feature | Basic | Advanced | Tại sao quan trọng? |
|---------|-------|----------|---------------------|
| Config | Hardcode | Env vars (`pydantic`) | Bảo mật tốt hơn, dễ thay đổi qua từng môi trường mà không cần sửa code. |
| Health check | Không có | Có (`/health`, `/ready`) | Cho phép hệ thống hoặc load balancer biết khi nào ứng dụng hoạt động tốt để điều chuyển requests (hoặc container bị crash để restart). |
| Logging | `print()` | JSON Structured | Tránh lộ secret, JSON format rất dễ để các tool aggregator/parse log như Elasticsearch, Loki đọc dữ liệu. |
| Shutdown | Đột ngột | Graceful Shutdown | Không làm hỏng hoặc mất request nào đang được thực thi dở dang khi tắt ứng dụng. |
| Host & Port | Cố định (localhost:8000) | Env var `PORT`, host `0.0.0.0` | Container có thể nhận giao tiếp từ bên ngoài bằng `0.0.0.0` và tuỳ chỉnh Port tự động trên Cloud deployment. |

---

## Part 2: Docker Containerization

**Exercise 2.1: Dockerfile cơ bản**
1. **Base image là gì?**: `python:3.11`.
2. **Working directory là gì?**: `/app` (thư mục chạy mặc định trong container lúc khởi tạo).
3. **Tại sao `COPY requirements.txt` trước?**: Nhằm tận dụng Docker layer caching. Nếu file requirements.txt không thay đổi, Docker sẽ không phải dùng thời gian chạy `RUN pip install` lần nữa.
4. **CMD vs ENTRYPOINT?**: `CMD` định nghĩa tham số lệnh mặc định (dễ bị override bằng lệnh khác khi gọi `docker run`). `ENTRYPOINT` định nghĩa core process bắt buộc phải chạy và khó override hơn.

**Exercise 2.3: Multi-stage build**
- **Stage 1 (builder) làm gì?**: Chỉ dùng để thiết lập trình biên dịch (như gcc), setup môi trường để build và cài Python packages phụ thuộc.
- **Stage 2 (runtime) làm gì?**: Dựng lên non-root user (appuser). Copy các site-packages đã cài sẵn từ step Builder qua (bỏ đi các libs hệ thống rác). Cuối cùng chuẩn bị khởi động môi trường.
- **Tại sao image nhỏ hơn?**: Stage 2 bỏ tất cả thư viện build của hệ điều hành, source code tải về của package, giúp bảo mật và giảm rủi ro về kích cỡ (từ ~1GB xuống < 500MB).

**Exercise 2.4: Docker Compose stack**
Các services được start: `agent`, `redis`, `qdrant`, `nginx`. Mọi traffic đi từ client HTTP yêu cầu vào Nginx, Nginx đóng vai trò là reverse proxy / Load balancer chuyển traffic xử lý cho replicas agent qua mạng internal bridge.

---

## Part 3: Cloud Deployment

- **Deploy Platforms:** Tích hợp với `render.yaml` (Render), `railway.toml` (Railway), thông qua việc inject environment logic (như tuỳ biến PORT thành Port deploy).

---

## Part 4: API Security

**Exercise 4.1: API Key authentication**
- **Được check ở đâu?**: Thông qua middleware dependency `verify_api_key(...)` được cài vào logic decorator endpoint `@app.post(..., Depends(verify_api_key))`.
- **Nếu sai API Key?**: Sẽ xuất hiện lỗi `HTTP 403 Forbidden` (hoặc `401 Unauthorized` nếu rỗng headers) làm ngắt kết nối.
- **Làm sao rotate key?**: Đổi giá trị khai báo của key trong Variable Environment (ví dụ `AGENT_API_KEY`) trên server Production.

**Exercise 4.3: Rate limiting**
- **Algorithm nào được dùng?**: Sliding Window Counter.
- **Limit request**: `10 request/minutes` (User thông thường).
- **Làm sao bypass limit cho Admin?**: Gán token/vai trò quyền admin với thông số riêng (ví dụ khởi tạo RateLimiter parameter với `100 request/minutes` thay vì 10).

**Exercise 4.4: Cost guard logic (Redis Database)**
```python
import redis
from datetime import datetime

r = redis.Redis(decode_responses=True)

def check_budget(user_id: str, estimated_cost: float) -> bool:
    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"
    
    current = float(r.get(key) or 0)
    if current + estimated_cost > 10:  # Ngân sách là 10$/tháng
        return False
    
    r.incrbyfloat(key, estimated_cost)
    r.expire(key, 32 * 24 * 3600)  # TTL 32 days
    return True
```

---

## Part 5: Scaling & Reliability

**Exercise 5.1: Health checks logic**
- Khởi tạo Endpoint `/health` (Liveness) trả về `200 OK` (hoặc degraded) thể hiện Container có tiếp tục sống và app không bị đứng cứng ngắc.
- Khởi tạo Endpoint `/ready` (Readiness). Xử lý việc ứng dụng mới khởi động/Load database chưa xong, trả tín hiệu HTTP 503 cho Nginx biết đừng chuyển request tới con này.

**Exercise 5.3: Stateless design**
- **Anti-pattern:** Khai báo Dict `conversation_history = {}` lưu global in-memory. Request đầu bị đưa tới Server 1. Lúc Request sau đưa tới Server 2 (do scale ra 2 bản), User sẽ bị mất luồng chat vì Server 2 hoàn toàn không biết `conversation_history` đó.
- **Refactor Code (Best Practice):** Bắt buộc lưu lịch sử đoạn hội thoại ra DataStore riêng như `Redis`. (Ví dụ: `r.lrange(f"history:{user_id}", 0, -1)`).
