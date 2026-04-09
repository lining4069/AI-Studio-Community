import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";

import { useRegister } from "@/api/endpoints/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getErrorMessage } from "@/lib/data";
import { registerSchema, type RegisterSchema } from "@/lib/validators/auth";

export function RegisterForm() {
  const navigate = useNavigate();
  const register = useRegister();
  const form = useForm<RegisterSchema>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      username: "",
      password: "",
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    await register.mutateAsync({
      ...values,
      device_id: "desktop-web",
    });
    navigate("/home");
  });

  return (
    <form className="space-y-5" onSubmit={onSubmit}>
      <div className="space-y-2">
        <Label htmlFor="register-username">用户名</Label>
        <Input id="register-username" {...form.register("username")} />
        {form.formState.errors.username ? (
          <p className="text-xs text-rose-500">{form.formState.errors.username.message}</p>
        ) : null}
      </div>
      <div className="space-y-2">
        <Label htmlFor="register-password">密码</Label>
        <Input
          id="register-password"
          type="password"
          {...form.register("password")}
        />
        {form.formState.errors.password ? (
          <p className="text-xs text-rose-500">{form.formState.errors.password.message}</p>
        ) : null}
      </div>
      {register.error ? (
        <p className="rounded-2xl bg-rose-50 px-3 py-2 text-sm text-rose-600">
          {getErrorMessage(register.error, "注册失败，请检查输入或后端服务状态")}
        </p>
      ) : null}
      <Button className="w-full" type="submit" disabled={register.isPending}>
        {register.isPending ? "创建中..." : "创建账号"}
      </Button>
    </form>
  );
}
