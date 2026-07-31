import { useEffect, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";
import { useQuery } from "@tanstack/react-query";

import { ApiError } from "../../api/client";
import * as organizationsApi from "../../api/organizationsApi";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Spinner } from "../../components/ui/Spinner";
import { useAuth } from "../../hooks/useAuth";

const schema = z
  .object({
    fullName: z.string().max(150).optional(),
    password: z.string().min(8, "Password must be at least 8 characters").max(128),
    confirmPassword: z.string().min(1, "Please confirm your password"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

type FormValues = z.infer<typeof schema>;

export function AcceptInvitationPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const navigate = useNavigate();
  const { login: _login } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);

  const previewQuery = useQuery({
    queryKey: ["invitation-preview", token],
    queryFn: () => organizationsApi.previewInvitation(token),
    enabled: token.length >= 16,
    retry: false,
  });

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    setFormError(null);
  }, [token]);

  const onSubmit = async (values: FormValues) => {
    setFormError(null);
    try {
      await organizationsApi.acceptInvitation(token, {
        password: values.password,
        full_name: values.fullName,
      });
      // acceptInvitation already saves session; hard-nav so AuthProvider hydrates from storage.
      const org = previewQuery.data?.organization_name
        ? `?org=${encodeURIComponent(previewQuery.data.organization_name)}`
        : "";
      window.location.assign(`/auth/joining-organization${org}`);
    } catch (error) {
      setFormError(error instanceof ApiError ? error.message : "Unable to accept invitation.");
    }
  };

  if (!token) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Join an organization</h1>
        <Alert variant="warning" className="mt-5">
          Paste a full invitation link that includes a <code>token</code> query parameter, or ask your
          organization admin to resend the invite.
        </Alert>
        <p className="mt-6 text-sm text-text-muted">
          <Link to="/login" className="text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    );
  }

  if (previewQuery.isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner size="lg" />
      </div>
    );
  }

  if (previewQuery.isError || !previewQuery.data) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Invitation unavailable</h1>
        <Alert variant="danger" className="mt-5">
          This invitation link is invalid or has been revoked.
        </Alert>
        <Button className="mt-6" onClick={() => navigate("/login")}>
          Go to sign in
        </Button>
      </div>
    );
  }

  const preview = previewQuery.data;
  if (preview.is_expired || preview.status !== "pending") {
    return (
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Invitation expired</h1>
        <Alert variant="warning" className="mt-5">
          This invitation for <strong>{preview.organization_name}</strong> is no longer valid. Ask an
          organization admin to send a new link.
        </Alert>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-text-primary">Join {preview.organization_name}</h1>
      <p className="mt-1.5 text-sm text-text-secondary">
        You were invited as <strong>{preview.role.replace(/_/g, " ")}</strong> ({preview.email}).
        {preview.user_exists
          ? " Enter your existing password to join."
          : " Create a password to join this workspace."}
      </p>

      {formError && (
        <Alert variant="danger" className="mt-5">
          {formError}
        </Alert>
      )}

      <form className="mt-6 flex flex-col gap-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        {!preview.user_exists && (
          <Input label="Full name" required error={errors.fullName?.message} {...register("fullName")} />
        )}
        <Input
          type="password"
          label={preview.user_exists ? "Password" : "Create password"}
          required
          error={errors.password?.message}
          {...register("password")}
        />
        <Input
          type="password"
          label="Confirm password"
          required
          error={errors.confirmPassword?.message}
          {...register("confirmPassword")}
        />
        <Button type="submit" size="lg" isLoading={isSubmitting} className="w-full">
          Join organization
        </Button>
      </form>
    </div>
  );
}
