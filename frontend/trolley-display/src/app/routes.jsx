
import { Navigate, Route, Routes } from "react-router-dom";
import App from "./App.jsx";
import Login from "./Login.jsx";
import Register from "./Register.jsx";

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/shopping" element={<App />} />
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

export default AppRoutes;
