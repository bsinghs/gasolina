import { useState, type FormEvent } from "react";
import { AUTH_MODE, useAuth } from "../auth/AuthProvider";

// People created by `make demo` (services/api/scripts/seed_demo.py)
const DEMO_PEOPLE = [
  { label: "Owner", email: "owner@example.com" },
  { label: "Co-owner", email: "coowner@example.com" },
  { label: "Employee · Route 9", email: "employee1@example.com" },
  { label: "Employee · Main Street", email: "employee2@example.com" },
];

export function SignInPage() {
  const { signInWithGoogle, sendEmailLink, devSignIn } = useAuth();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onEmail = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      if (AUTH_MODE === "dev") await devSignIn(email);
      else {
        await sendEmailLink(email);
        setSent(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't sign in");
    }
  };

  return (
    <main className="signin">
      <div className="signin-box">
        <div className="eyebrow">SHIFT CLOSE</div>
        <h1>Close the day in two minutes.</h1>
        <p>Submit your store's daily sales worksheet. The owner reviews it and it goes straight to the books.</p>

        {AUTH_MODE === "supabase" && (
          <button className="btn btn-google" onClick={signInWithGoogle}>Continue with Google</button>
        )}

        <form onSubmit={onEmail} className="stack" style={{ gap: 10, marginTop: 8 }}>
          <label className="label-stack" style={{ color: "#9fb2b7" }}>
            {AUTH_MODE === "dev" ? "Your email (test mode)" : "Or use any email"}
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </label>
          <button className="btn btn-primary btn-block" type="submit">
            {AUTH_MODE === "dev" ? "Sign in" : "Email me a sign-in link"}
          </button>
        </form>

        {sent && <p>Check your inbox for a sign-in link.</p>}
        {error && <p style={{ color: "#f3b3ad" }}>{error}</p>}
        {AUTH_MODE === "dev" && (
          <div className="stack" style={{ gap: 8, marginTop: 8 }}>
            <p style={{ fontSize: 12, color: "#9fb2b7" }}>Demo mode: pick who you want to be</p>
            {DEMO_PEOPLE.map((p) => (
              <button key={p.email} className="btn btn-ghost" style={{ justifyContent: "space-between" }} onClick={() => devSignIn(p.email)}>
                <span>{p.label}</span><span style={{ fontWeight: 400, fontSize: 12, color: "#4b5d63" }}>{p.email}</span>
              </button>
            ))}
          </div>
        )}
        <p style={{ fontSize: 12, color: "#9fb2b7", textAlign: "center" }}>Only people your manager has added can sign in.</p>
      </div>
    </main>
  );
}

export function NotInvitedPage() {
  const { signOut } = useAuth();
  return (
    <main className="signin">
      <div className="signin-box">
        <h1>Almost there</h1>
        <p>You're signed in, but your email isn't on the list yet. Ask the owner or your manager to add you, then sign in again.</p>
        <button className="btn btn-primary btn-block" onClick={signOut}>Use a different email</button>
      </div>
    </main>
  );
}
