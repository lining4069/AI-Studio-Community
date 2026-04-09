import { Link } from "react-router-dom";

import { LoginForm } from "@/features/auth/login-form";
import { AuthShell } from "@/features/auth/auth-shell";

export function LoginRoute() {
  return (
    <AuthShell
      eyebrow="AI Studio"
      title="欢迎回来"
      description="登录后即可进入你的知识库、助手与系统配置工作台。"
      gradient="bg-[linear-gradient(160deg,#f8fbff_0%,#eef4ff_50%,#f9fafb_100%)]"
      footer={
        <>
          还没有账号？
          <Link className="ml-2 font-medium text-sky-600" to="/register">
            去注册
          </Link>
        </>
      }
    >
      <LoginForm />
    </AuthShell>
  );
}
