import { SignIn } from "@clerk/nextjs";

export default function Page() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-accent-primary">YCK Ads Dashboard</h1>
          <p className="mt-2 text-sm text-text-muted">Sign in to your ad performance engine</p>
        </div>
        <SignIn />
      </div>
    </div>
  );
}
