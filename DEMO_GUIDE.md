# Hướng Dẫn Demo Code Lab (Part 1 -> Part 5)

Dưới đây là các lệnh để bạn tự tay chạy thử (demo) và kiểm chứng các tính năng trong Lab. Bạn hãy mở Terminal (trong thư mục `batch02-day12_cloud_infras_and_deployment`) và chạy lần lượt các bước sau:

---

## 🟢 Part 1: Localhost vs Production (Chạy Python cơ bản)

Mục tiêu: Thấy sự khác biệt giữa code chạy kiểu "Basic" và "Advanced".

**1. Demo bản Basic (Anti-patterns):**
```bash
cd 01-localhost-vs-production/develop
pip install -r requirements.txt
python app.py
```
Mở terminal khác và test (Lưu ý: API Key bị lộ trong console log của server):
```bash
curl -X POST "http://localhost:8000/ask?question=hello"
```
Nhấn `Ctrl+C` ở terminal chạy server để tắt.

**2. Demo bản Advanced (12-Factor App):**
```bash
cd ../production
pip install -r requirements.txt
python app.py
```
Test Endpoint `/health` và `/ask` (Lưu ý: Console trả ra dạng JSON log bảo mật):
```bash
curl http://localhost:8000/health
curl -X POST -H "Content-Type: application/json" -d '{"question": "What is AI?"}' "http://localhost:8000/ask"
```
Nhấn `Ctrl+C` để trải nghiệm "Graceful Shutdown" (Server sẽ thông báo chờ xử lý nốt yêu cầu rồi mới đóng).

---

## 🐳 Part 2: Docker Containerization

Mục tiêu: Đóng gói toàn bộ code vào Docker để đảm bảo "chạy được ở mọi nơi".

**1. Demo build Docker thuần:**
Quay lại thư mục gốc dự án:
```bash
cd ../../
# Build Image bản production (Multi-stage)
docker build -f 02-docker/production/Dockerfile -t agent-production .

# Kiểm tra dung lượng image (bạn sẽ thấy nó rất nhỏ)
docker images | grep agent-production

# Chạy thử
docker run -p 8000:8000 agent-production
```

**2. Demo Docker Compose (Stack đầy đủ Agent + Redis + Nginx):**
Khởi chạy hệ thống hoàn chỉnh:
```bash
cd 02-docker/production
docker compose up -d
```
Test thông qua Nginx Load Balancer (chạy cổng 80):
```bash
curl http://localhost/health
```
Kết thúc demo part 2:
```bash
docker compose down
cd ../../
```

---

## ☁️ Part 3: Cloud Deployment

Mục tiêu: Đưa Agent có public URL bằng nền tảng cloud (Ví dụ: Railway).

1. Cài đặt Railway CLI (nếu bạn sử dụng Node.js):
```bash
npm i -g @railway/cli
```
2. Đăng nhập và làm theo các bước tải lên Cloud:
```bash
cd 03-cloud-deployment/railway
railway login
railway init
railway up
```
3. Xem public URL để test:
```bash
railway domain
```
Cuối cùng test qua public Url: `curl http://<your-railway-domain>/health`

---

## 🔒 Part 4: API Security

Mục tiêu: Khóa API, chỉ ai dùng API Key mới request được.

```bash
cd 04-api-gateway/develop
pip install -r requirements.txt
# Set API KEY lúc khởi động server
AGENT_API_KEY=my-super-secret-key python app.py
```
**Test trường hợp KHÔNG có khóa (Báo lỗi 401 Unauthorized):**
```bash
curl -X POST -H "Content-Type: application/json" -d '{"question":"hello"}' "http://localhost:8000/ask"
```
**Test trường hợp CÓ cung cấp khóa (Sẽ thành công 200 OK):**
```bash
curl -X POST -H "X-API-Key: my-super-secret-key" -H "Content-Type: application/json" -d '{"question":"hello"}' "http://localhost:8000/ask"
```
Tắt bằng `Ctrl+C`.

---

## ⚖️ Part 5: Scaling & Reliability

Mục tiêu: Khả năng mở rộng server từ 1 thành 3 bằng Load Balancer.

```bash
cd ../../05-scaling-reliability/production
```
Giả định bạn muốn chịu tải lớn, bạn có thể "Scale" Agent thành 3 Server chạy cùng lúc (Redis và Nginx sẽ hỗ trợ việc cân bằng):
```bash
docker compose up --scale agent=3 -d
```

**Test Load Balancing:**
Bạn chạy vòng lặp gửi 10 requests cùng lúc, và xem log để thấy Nginx tự chia đều 10 requests này cho cả 3 Con Agent xử lý (Thay vì 1 con phải gánh hết).
```bash
# Gửi 10 requests
for i in {1..10}; do
  curl -X POST http://localhost/ask -H "Content-Type: application/json" -d "{\"question\": \"Test $i\"}"
done

# Tại terminal kiểm tra log bạn sẽ thấy 3 tiến trình Agent1, Agent2, Agent3 nhận request chéo nhau
docker compose logs agent
```

Kết thúc mô hình khi demo xong:
```bash
docker compose down
```
