# File: webhook_server.py -> bỏ
# Chức năng: F01 - Tiếp nhận sự kiện từ Git (GitHub)
# Công nghệ: Python, Flask
# Mục đích: Lắng nghe webhook, xác thực HMAC, và uỷ quyền xử lý cho main_processor.

import os
import hmac
import hashlib
from flask import Flask, request, Response, jsonify
from main_processor import process_pull_request

app = Flask(__name__)

# --- Cấu hình bảo mật ---
# Bắt buộc cấu hình trong môi trường production.
WEBHOOK_SECRET = os.environ.get('GITHUB_WEBHOOK_SECRET', '')
# Cho phép bỏ qua xác thực khi DEV (ví dụ chạy demo): set ALLOW_UNVERIFIED_WEBHOOKS=1
ALLOW_UNVERIFIED = os.environ.get('ALLOW_UNVERIFIED_WEBHOOKS', '0') == '1'


def verify_signature(payload_body: bytes, secret_token: str, signature_header: str) -> bool:
    """
    Xác thực chữ ký webhook của GitHub (X-Hub-Signature-256).
    Cú pháp header: "sha256=<hex>"
    """
    if not signature_header:
        app.logger.warning("Missing 'X-Hub-Signature-256' header")
        return False
    if not secret_token:
        app.logger.error("GITHUB_WEBHOOK_SECRET is not set on the server")
        return False

    mac = hmac.new(secret_token.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
    expected = "sha256=" + mac.hexdigest()
    # So sánh chống timing attack
    return hmac.compare_digest(expected, signature_header)


@app.route('/healthz', methods=['GET'])
def healthz():
    return jsonify({"status": "ok"}), 200


@app.route('/webhook', methods=['POST'])
def github_webhook_handler():
    """
    Endpoint tiếp nhận webhook từ GitHub.
    - Xác thực chữ ký
    - Lọc sự kiện & action
    - Uỷ quyền xử lý cho process_pull_request(payload)
    """

    # 1) Đảm bảo body không rỗng và JSON hợp lệ
    raw_body = request.get_data(cache=True, as_text=False) or b''
    payload = request.get_json(silent=True)
    if payload is None:
        app.logger.error("Invalid JSON payload")
        return Response("Invalid JSON", status=400)

    # 2) Lấy loại sự kiện
    event_type = request.headers.get('X-GitHub-Event', '')
    delivery_id = request.headers.get('X-GitHub-Delivery', '')
    app.logger.info(f"Incoming event={event_type} delivery={delivery_id}")

    # 3) Ping event (GitHub test ping)
    if event_type == 'ping':
        return jsonify({"msg": "pong"}), 200

    # 4) Xác thực chữ ký (nếu không bật chế độ cho phép bỏ qua)
    signature = request.headers.get('X-Hub-Signature-256')
    if not ALLOW_UNVERIFIED:
        if not verify_signature(raw_body, WEBHOOK_SECRET, signature):
            app.logger.error("Invalid signature. Request rejected.")
            return Response("Invalid signature", status=403)
    else:
        if not WEBHOOK_SECRET:
            app.logger.warning("Running without webhook signature verification (DEV mode).")

    # 5) Chỉ xử lý sự kiện pull_request
    if event_type != 'pull_request':
        app.logger.info(f"Ignoring event type: {event_type}")
        return Response(f"Ignored event: {event_type}", status=200)

    # 6) Lọc action cần xử lý
    action = payload.get('action')
    allowed_actions = {'opened', 'synchronize', 'reopened', 'ready_for_review'}
    if action not in allowed_actions:
        app.logger.info(f"Ignoring pull_request action: {action}")
        return Response(f"Ignored action: {action}", status=200)

    # 7) Log ngắn gọn
    pr_number = payload.get('number')
    repo_full_name = payload.get('repository', {}).get('full_name') or payload.get('repository', {}).get('name')
    head_sha = payload.get('pull_request', {}).get('head', {}).get('sha')
    app.logger.info(f"Accepted PR #{pr_number} in {repo_full_name}, head_sha={head_sha}, action={action}")

    # 8) Uỷ quyền xử lý (đồng bộ cho đồ án; production nên dùng queue như Celery/RQ)
    try:
        process_pull_request(payload)
    except Exception as e:
        app.logger.exception(f"process_pull_request error: {e}")
        # Báo nhận (202) để GitHub không retry liên tục, nhưng log lỗi để xử lý nội bộ
        return Response("Accepted with processing error", status=202)

    # 9) Phản hồi
    return Response("Accepted for processing", status=202)


if __name__ == '__main__':
    # Dev server. Production => WSGI server (Gunicorn/Uvicorn) + reverse proxy (Nginx).
    # Cấu hình host='0.0.0.0' để nhận từ ngoài nếu cần.
    app.run(host='0.0.0.0', port=5000, debug=True)
