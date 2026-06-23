# Supabase Operator Auth Setup

The desktop app does not have a server-login screen. Operators sign in with a
normal Supabase Auth email/password account. The app stores the Supabase Auth
session token locally, not the operator password.

## Create The Operator User

1. Open the Supabase project:
   `https://supabase.com/dashboard/project/ofogstpjheigpnsmnlxn`
2. Go to `Authentication` > `Users`.
3. Select `Add user`.
4. Enter the operator email used in `ALLOWED_OPERATOR_EMAILS`.
5. Set a strong operator password.
6. Mark the email as confirmed if the dashboard offers that option.

## Required Secret Alignment

The email must exactly match one of the comma-separated values in the Supabase
Edge Function secret:

```text
ALLOWED_OPERATOR_EMAILS=operator@example.com
```

If the user can sign in but Riot actions return `Operator is not authorized`,
the Supabase Auth email and `ALLOWED_OPERATOR_EMAILS` do not match.

## Desktop App Login

In the desktop app settings:

- Enter the operator email.
- Enter the operator password.
- Select the authentication/apply settings button.

The password is used only for Supabase Auth sign-in and is not persisted by the
desktop app.

## Offboarding

When an operator should no longer have access:

1. Remove or disable the Supabase Auth user.
2. Remove that email from `ALLOWED_OPERATOR_EMAILS`.
3. Ask remaining operators to sign in again if access policy changed.
