// src/api/apiClient.js
import axios from "axios";
import { getToken } from "../utils/storage";

const apiClient = axios.create({
  // Với Vite proxy: /api -> http://localhost:8001 hoặc 8002 tuỳ bạn cấu hình
  // Vite config:  /api -> http://localhost:8001  (hoặc 8002)
  baseURL: "", // để nguyên, các request vẫn dùng "/api/..."
  timeout: 10000,
});

// ✅ Gắn Authorization header trước mỗi request
apiClient.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      // Nếu backend dùng kiểu khác (vd: "Token xxx"), chỉnh chuỗi dưới
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ✅ Xử lý response
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      console.warn("401 Unauthorized - token hết hạn hoặc không hợp lệ");
      // Ví dụ xử lý sau này:
      // clearAllTokens();
      // window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default apiClient;
