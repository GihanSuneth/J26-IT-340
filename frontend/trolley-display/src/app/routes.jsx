import { Navigate, Route, Routes } from "react-router-dom";
import App from "./App.jsx";
import Login from "./Login.jsx";
import Register from "./Register.jsx";
import RecommendationsPage from "./RecommendationsPage.jsx";

function RequireAuth({ children }) {
  const token = localStorage.getItem("access_token");
  const rawUser = localStorage.getItem("user");
  let user = null;
  try {
    user = rawUser ? JSON.parse(rawUser) : null;
  } catch {
    user = null;
  }

  if (!token || !user) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/shopping"
        element={<RequireAuth><App /></RequireAuth>}
      />
      <Route
        path="/recommendations"
        element={<RequireAuth><RecommendationsPage /></RequireAuth>}
      />
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

export default AppRoutes;
