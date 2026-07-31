import { Outlet } from "react-router-dom";

import { BrandLogo } from "../components/brand/BrandLogo";
import { AuthVisualPanel } from "./AuthVisualPanel";

export function AuthLayout() {
  return (
    <div className="grid min-h-screen grid-cols-1 bg-background lg:grid-cols-2">
      <div className="flex flex-col justify-center px-6 py-10 sm:px-12 lg:px-16">
        <div className="brand-form-enter mx-auto w-full max-w-sm">
          <div className="mb-8 flex justify-center sm:justify-start">
            <BrandLogo variant="full" size="md" priority animated />
          </div>
          <Outlet />
        </div>
      </div>

      <AuthVisualPanel />
    </div>
  );
}
