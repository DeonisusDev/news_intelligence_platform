import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthError } from "@/api/auth";
import { useLogin, useRegister } from "@/hooks/useAuth";

interface AuthDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type Mode = "login" | "register";

export function AuthDialog({ open, onOpenChange }: AuthDialogProps) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loginMutation = useLogin();
  const registerMutation = useRegister();
  const pending = loginMutation.isPending || registerMutation.isPending;

  function reset() {
    setEmail("");
    setPassword("");
    setError(null);
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset();
    onOpenChange(next);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      if (mode === "login") {
        await loginMutation.mutateAsync({ email, password });
        handleOpenChange(false);
      } else {
        await registerMutation.mutateAsync({ email, password });
        await loginMutation.mutateAsync({ email, password });
        handleOpenChange(false);
      }
    } catch (err) {
      setError(err instanceof AuthError ? err.message : "Something went wrong.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>{mode === "login" ? "Log in" : "Create an account"}</DialogTitle>
          <DialogDescription>
            {mode === "login"
              ? "Welcome back."
              : "Just an email and password - nothing else is collected."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="auth-email">Email</Label>
            <Input
              id="auth-email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="auth-password">Password</Label>
            <Input
              id="auth-password"
              type="password"
              required
              minLength={8}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <Button type="submit" disabled={pending} className="mt-1">
            {pending ? "Please wait..." : mode === "login" ? "Log in" : "Sign up"}
          </Button>

          <button
            type="button"
            className="text-sm text-muted-foreground hover:text-foreground hover:underline"
            onClick={() => {
              setError(null);
              setMode((m) => (m === "login" ? "register" : "login"));
            }}
          >
            {mode === "login" ? "Need an account? Sign up" : "Already have an account? Log in"}
          </button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
