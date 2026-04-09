import { Navigate, Outlet, useLocation } from "react-router-dom";

import { authStorage } from "@/lib/storage";

export function AuthGuard() {
  const location = useLocation();

  if (!authStorage.hasAccessToken()) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
