import { Link } from "react-router-dom";

import { RegisterForm } from "@/features/auth/register-form";
import { AuthShell } from "@/features/auth/auth-shell";

export function RegisterRoute() {
  return (
    <AuthShell
      eyebrow="创建账户"
      title="开始构建你的 AI 工作台"
      description="注册后即可把知识库、Agent 与系统能力配置收进统一桌面工作台。"
      gradient="bg-[linear-gradient(160deg,#fefcfb_0%,#eef4ff_50%,#f7fafc_100%)]"
      footer={
        <>
          已有账号？
          <Link className="ml-2 font-medium text-sky-600" to="/login">
            返回登录
          </Link>
        </>
      }
    >
      <RegisterForm />
    </AuthShell>
  );
}
