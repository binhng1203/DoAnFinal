import React, { useState } from "react";
import { EyeIcon, EyeSlashIcon } from "@heroicons/react/24/outline";
import { useNavigate } from "react-router-dom";
import ROUTES from "../../routes/routes";

export default function SignupPage() {
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (
      !fullName.trim() ||
      !username.trim() ||
      !email.trim() ||
      !password ||
      !confirmPassword
    ) {
      setError("Please fill in all fields.");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    try {
      setLoading(true);

      const body = {
        fullname: fullName.trim(),
        username: username.trim(),
        email: email.trim(),
        password: password,
      };
      const res = await fetch("/api/v1/auth/register", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });


      if (!res.ok) {
        // backend có thể trả message, nếu không thì dùng message mặc định
        let msg = "Sign up failed. Please try again.";
        try {
          const data = await res.json();
          if (data?.message) msg = data.message;
        } catch (_) {}
        throw new Error(msg);
      }

      const data = await res.json();
      console.log("Signup success:", data);

      // Đăng ký xong chuyển sang màn login
      navigate(ROUTES.LOGIN);
    } catch (err) {
      console.error(err);
      setError(err.message || "Sign up failed. Please try again.");
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
              Create your account
            </h2>
            <p className="text-sm md:text-base text-indigo-100 max-w-sm">
              Join the platform and start collaborating with your team in
              minutes.
            </p>
          </div>

          <div className="mt-8">
            <div className="bg-white/10 rounded-2xl p-4 md:p-5 backdrop-blur">
              <p className="text-sm md:text-base text-indigo-50 italic mb-3">
                “Onboarding new teammates has never been easier. The setup is
                incredibly fast.”
              </p>
              <div>
                <p className="text-sm font-semibold">Alex Nguyen</p>
                <p className="text-xs text-indigo-100">Product Manager</p>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT PANEL - FORM */}
        <div className="md:w-1/2 px-6 py-8 md:px-10 md:py-10 flex items-center">
          <div className="w-full">
            <h2 className="text-2xl font-semibold text-slate-900">
              Sign up
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Create an account to get started
            </p>

            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              {/* Full name */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Full name
                </label>
                <input
                  type="text"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                  placeholder="Enter your fullname"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </div>

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

              {/* Email */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Email Address
                </label>
                <input
                  type="email"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                  placeholder="Enter your email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
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
                    placeholder="Create a password"
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
              </div>

              {/* Confirm password */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Confirm password
                </label>
                <div className="relative">
                  <input
                    type={showConfirm ? "text" : "password"}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 pr-10 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                    placeholder="Re-enter your password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm((prev) => !prev)}
                    className="absolute inset-y-0 right-2 flex items-center text-slate-400 hover:text-slate-600"
                  >
                    {showConfirm ? (
                      <EyeSlashIcon className="w-5 h-5" />
                    ) : (
                      <EyeIcon className="w-5 h-5" />
                    )}
                  </button>
                </div>
              </div>

              {error && (
                <p className="text-xs text-red-500 mt-1">{error}</p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="mt-2 w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {loading ? "Creating account..." : "Create account"}
              </button>
            </form>

            <p className="mt-4 text-xs text-slate-500 text-center">
              Already have an account?{" "}
              <button
                type="button"
                className="font-medium text-indigo-600 hover:underline"
                onClick={() => navigate(ROUTES.LOGIN)}
              >
                Log in
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
