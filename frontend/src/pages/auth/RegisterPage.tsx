import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";

import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { useAuth } from "../../hooks/useAuth";

const schema = z
  .object({
    fullName: z.string().min(1, "Full name is required").max(150),
    email: z.string().min(1, "Email is required").email("Enter a valid email address"),
    password: z
      .string()
      .min(8, "Password must be at least 8 characters")
      .max(128),
    confirmPassword: z.string().min(1, "Please confirm your password"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

type FormValues = z.infer<typeof schema>;

export function RegisterPage() {
  const { register: registerUser, login } = useAuth();
  const navigate = useNavigate();
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const password = watch("password") ?? "";

  const onSubmit = async (values: FormValues) => {
    setFormError(null);
    try {
      await registerUser({
        full_name: values.fullName,
        email: values.email,
        password: values.password,
      });
      setSuccess(true);
      await login({ email: values.email, password: values.password });
      navigate("/dashboard", { replace: true });
    } catch (error) {
      if (error instanceof ApiError) {
        setFormError(error.message);
      } else {
        setFormError("Unable to create your account. Please try again.");
      }
    }
  };

  const requirements = [
    { label: "At least 8 characters", met: password.length >= 8 },
    { label: "Contains a number", met: /\d/.test(password) },
    { label: "Contains a letter", met: /[a-zA-Z]/.test(password) },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold text-text-primary">Create your account</h1>
      <p className="mt-1.5 text-sm text-text-secondary">
        Start diagnosing CI/CD failures with grounded, explainable AI analysis.
      </p>

      {formError && (
        <Alert variant="danger" className="mt-5">
          {formError}
        </Alert>
      )}
      {success && !formError && (
        <Alert variant="success" className="mt-5">
          Account created. Signing you in…
        </Alert>
      )}

      <form className="mt-6 flex flex-col gap-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <Input
          label="Full name"
          autoComplete="name"
          required
          error={errors.fullName?.message}
          {...register("fullName")}
        />
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
          autoComplete="new-password"
          required
          error={errors.password?.message}
          {...register("password")}
        />
        <ul className="-mt-1 flex flex-col gap-1 text-xs">
          {requirements.map((requirement) => (
            <li
              key={requirement.label}
              className={`flex items-center gap-1.5 ${requirement.met ? "text-success" : "text-text-muted"}`}
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              {requirement.label}
            </li>
          ))}
        </ul>
        <Input
          type="password"
          label="Confirm password"
          autoComplete="new-password"
          required
          error={errors.confirmPassword?.message}
          {...register("confirmPassword")}
        />
        <Button type="submit" size="lg" isLoading={isSubmitting} className="mt-2 w-full">
          Create account
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-text-muted">
        Already have an account?{" "}
        <Link to="/login" className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
