import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useMutation } from "@tanstack/react-query";
import { z } from "zod";

import { changePassword } from "../../api/authApi";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";

const schema = z
  .object({
    current_password: z.string().min(1, "Current password is required"),
    new_password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string().min(1, "Please confirm your new password"),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type FormValues = z.infer<typeof schema>;

export function SecuritySettingsPage() {
  const [success, setSuccess] = useState(false);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      changePassword({ current_password: values.current_password, new_password: values.new_password }),
    onSuccess: () => {
      setSuccess(true);
      reset();
    },
  });

  return (
    <Card>
      <CardHeader title="Password" subtitle="Change the password used to sign in." />
      <CardBody>
        {success && (
          <Alert variant="success" className="mb-4">
            Password updated successfully.
          </Alert>
        )}
        {mutation.isError && (
          <Alert variant="danger" className="mb-4">
            {mutation.error instanceof ApiError ? mutation.error.message : "Failed to update password."}
          </Alert>
        )}
        <form
          onSubmit={handleSubmit((values) => {
            setSuccess(false);
            mutation.mutate(values);
          })}
          className="flex max-w-md flex-col gap-4"
          noValidate
        >
          <Input
            type="password"
            label="Current password"
            autoComplete="current-password"
            required
            error={errors.current_password?.message}
            {...register("current_password")}
          />
          <Input
            type="password"
            label="New password"
            autoComplete="new-password"
            required
            error={errors.new_password?.message}
            {...register("new_password")}
          />
          <Input
            type="password"
            label="Confirm new password"
            autoComplete="new-password"
            required
            error={errors.confirm_password?.message}
            {...register("confirm_password")}
          />
          <div className="flex justify-end">
            <Button type="submit" isLoading={mutation.isPending}>
              Update password
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}
