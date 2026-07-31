import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { useAuth } from "../../hooks/useAuth";

const schema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setFormError(null);
    try {
      await login(values);
      const next = searchParams.get("next");
      navigate(next && next.startsWith("/") ? next : "/dashboard", { replace: true });
    } catch (error) {
      if (error instanceof ApiError) {
        setFormError(error.message);
      } else {
        setFormError("Unable to sign in. Please try again.");
      }
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-text-primary">Welcome back</h1>
      <p className="mt-1.5 text-sm text-text-secondary">
        Sign in to review incidents, evidence, and AI-generated recommendations.
      </p>

      {formError && (
        <Alert variant="danger" className="mt-5">
          {formError}
        </Alert>
      )}

      <form className="mt-6 flex flex-col gap-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <Input
          type="email"
          label="Email"
          autoComplete="email"
          required
          error={errors.email?.message}
          {...register("email")}
        />
        <Input
          type="password"
          label="Password"
          autoComplete="current-password"
          required
          error={errors.password?.message}
          {...register("password")}
        />
        <Button type="submit" size="lg" isLoading={isSubmitting} className="mt-2 w-full">
          Sign in
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-text-muted">
        Don&apos;t have a workspace?{" "}
        <Link to="/register" className="font-medium text-primary hover:underline">
          Create one
        </Link>
        {" · "}
        <Link to="/invitations/accept" className="font-medium text-primary hover:underline">
          Join with invite
        </Link>
      </p>
    </div>
  );
}
