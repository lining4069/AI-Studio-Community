import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";

import { useLogin } from "@/api/endpoints/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getErrorMessage } from "@/lib/data";
import { loginSchema, type LoginSchema } from "@/lib/validators/auth";

export function LoginForm() {
  const navigate = useNavigate();
  const login = useLogin();
  const form = useForm<LoginSchema>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      username: "",
      password: "",
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    await login.mutateAsync({
      ...values,
      device_id: "desktop-web",
    });
    navigate("/home");
  });

  return (
    <form className="space-y-5" onSubmit={onSubmit}>
      <div className="space-y-2">
        <Label htmlFor="username">用户名</Label>
        <Input id="username" {...form.register("username")} />
        {form.formState.errors.username ? (
          <p className="text-xs text-rose-500">{form.formState.errors.username.message}</p>
        ) : null}
      </div>
      <div className="space-y-2">
        <Label htmlFor="password">密码</Label>
        <Input id="password" type="password" {...form.register("password")} />
        {form.formState.errors.password ? (
          <p className="text-xs text-rose-500">{form.formState.errors.password.message}</p>
        ) : null}
      </div>
      {login.error ? (
        <p className="rounded-2xl bg-rose-50 px-3 py-2 text-sm text-rose-600">
          {getErrorMessage(login.error, "登录失败，请检查用户名、密码或后端服务状态")}
        </p>
      ) : null}
      <Button className="w-full" type="submit" disabled={login.isPending}>
        {login.isPending ? "登录中..." : "登录"}
      </Button>
    </form>
  );
}
