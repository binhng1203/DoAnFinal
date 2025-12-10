// src/pages/auth/LoginPage.jsx
import React, { useState } from "react";
import { EyeIcon, EyeSlashIcon } from "@heroicons/react/24/outline";
import { useNavigate } from "react-router-dom";
import ROUTES from "../../routes/routes";
import {
  setToken,
  setRefreshToken,
  clearRefreshToken,
} from "../../utils/storage";
import apiClient from "../../services/apiClient";

export default function LoginPage() {
  const navigate = useNavigate();

  const [username, setUsername] = useState(""); // API dùng username
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!username.trim() || !password.trim()) {
      setError("Please fill in all fields.");
      return;
    }

    try {
      setLoading(true);

      const payload = {
        username: username.trim(),
        password: password,
      };

      // Vite proxy: /api -> http://localhost:8001
      // => apiClient.post("/api/v1/auth/login", ...) sẽ gọi đúng http://localhost:8001/api/v1/auth/login
      const data = await apiClient.post("/api/v1/auth/login", payload);
      // do interceptor response đã .data rồi, nên data chính là body:
      // { access_token, message, user }

      console.log("Login success:", data);

      if (!data?.access_token) {
        throw new Error("Invalid server response: missing access_token.");
      }

      // Lưu access token
      setToken(data.access_token);

      // Nếu sau này backend trả thêm refresh_token thì tự lưu
      if (data.refresh_token) {
        setRefreshToken(data.refresh_token);
      } else {
        // hiện tại API sample không có refresh_token → clear refresh cũ
        clearRefreshToken();
      }

      // Lưu thông tin user (tuỳ bạn dùng sau này cho header / profile)
      if (data.user) {
        localStorage.setItem("user", JSON.stringify(data.user));
      }

      // Điều hướng sang Dashboard sau khi login
      navigate(ROUTES.DASHBOARD);
    } catch (err) {
      console.error(err);

      // Lấy message từ backend nếu có
      const msg =
        err?.response?.data?.message ||
        err?.message ||
        "Login failed. Please try again.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100 px-4">
      <div className="max-w-5xl w-full bg-white rounded-3xl shadow-lg overflow-hidden flex flex-col md:flex-row">
        {/* LEFT PANEL */}
        <div className="md:w-1/2 bg-gradient-to-br from-indigo-600 via-purple-600 to-fuchsia-500 text-white p-8 md:p-10 flex flex-col justify-between">
          <div>
            <h2 className="text-2xl md:text-3xl font-semibold mb-2">
              Welcome to Platform
            </h2>
            <p className="text-sm md:text-base text-indigo-100 max-w-sm">
              Streamline your workflow with our powerful platform designed for
              modern teams.
            </p>
          </div>

          <div className="mt-8">
            <div className="bg-white/10 rounded-2xl p-4 md:p-5 backdrop-blur">
              <p className="text-sm md:text-base text-indigo-50 italic mb-3">
                “This platform has transformed how our team collaborates. Highly
                recommended!”
              </p>
              <div>
                <p className="text-sm font-semibold">Sarah Johnson</p>
                <p className="text-xs text-indigo-100">CEO, TechCorp</p>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT PANEL - FORM */}
        <div className="md:w-1/2 px-6 py-8 md:px-10 md:py-10 flex items-center">
          <div className="w-full">
            <h2 className="text-2xl font-semibold text-slate-900">
              Welcome back
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Sign in to your account to continue
            </p>

            {/* SSO BUTTONS (mock UI) */}
            <div className="mt-6 space-y-3">
              <button className="w-full inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50">
                <span className="text-red-500 text-lg">G</span>
                <span>Sign in with Google</span>
              </button>
              <button className="w-full inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50">
                <span className="text-slate-800 text-lg"></span>
                <span>Sign in with GitHub</span>
              </button>
              <button className="w-full inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50">
                <span className="text-indigo-600 text-lg">◆</span>
                <span>Sign in with SAML (SSO)</span>
              </button>
            </div>

            {/* OR DIVIDER */}
            <div className="my-5 flex items-center">
              <div className="h-px flex-1 bg-slate-200" />
              <span className="px-3 text-xs uppercase tracking-wide text-slate-400">
                or
              </span>
              <div className="h-px flex-1 bg-slate-200" />
            </div>

            {/* FORM */}
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Username */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Username
                </label>
                <input
                  type="text"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                  placeholder="Enter your username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>

              {/* Password */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 pr-10 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    className="absolute inset-y-0 right-2 flex items-center text-slate-400 hover:text-slate-600"
                  >
                    {showPassword ? (
                      <EyeSlashIcon className="w-5 h-5" />
                    ) : (
                      <EyeIcon className="w-5 h-5" />
                    )}
                  </button>
                </div>
                <div className="mt-1 text-right">
                  <button
                    type="button"
                    className="text-xs text-indigo-600 hover:underline"
                  >
                    Forgot password?
                  </button>
                </div>
              </div>

              {error && <p className="text-xs text-red-500 mt-1">{error}</p>}

              <button
                type="submit"
                disabled={loading}
                className="mt-2 w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {loading ? "Logging in..." : "Log in"}
              </button>
            </form>

            <p className="mt-4 text-xs text-slate-500 text-center">
              Don’t have an account?{" "}
              <button
                type="button"
                className="font-medium text-indigo-600 hover:underline"
                onClick={() => navigate(ROUTES.SIGNUP)}
              >
                Sign up
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
