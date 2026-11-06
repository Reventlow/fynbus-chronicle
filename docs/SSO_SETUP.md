# Office 365 SSO Setup Guide

This guide covers configuring Office 365 (Microsoft Entra ID / Azure AD) Single Sign-On for FynBus Chronicle.

## Prerequisites

- Azure AD / Microsoft Entra ID admin access
- FynBus Chronicle deployed with accessible URL

## Step 1: Register Application in Azure

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Microsoft Entra ID** (formerly Azure Active Directory)
3. Click **App registrations** → **New registration**

### Application Registration

- **Name**: Chronicle SSO. Use an app of its own, separate from the one with `Mail.Send` for Graph mail and from *Chronicle Planner*: this app's secret lives in the web container, so it should carry nothing but sign-in.
- **Supported account types**: Accounts in this organizational directory only (Single tenant)
- **Redirect URI**:
  - Type: Web
  - URL: `https://chronicle.fynbus.net/allauth/microsoft/login/callback/` (allauth is mounted at `/allauth/`, not `/accounts/`; keep the trailing slash)

Click **Register**.

## Step 2: Configure Authentication

1. In your registered app, go to **Authentication**
2. Verify the redirect URI is correct
3. Under **Implicit grant and hybrid flows**, ensure both are **unchecked** (we use authorization code flow)
4. Click **Save**

## Step 3: Create Client Secret

1. Go to **Certificates & secrets**
2. Click **New client secret**
3. Add description: "FynBus Chronicle Production"
4. Choose expiration (recommend 12 months, and a calendar reminder to rotate it)
5. Click **Add**
6. **Copy the secret value immediately** - it won't be shown again!

## Step 4: Configure API Permissions

1. Go to **API permissions**
2. Click **Add a permission**
3. Select **Microsoft Graph**
4. Select **Delegated permissions**
5. Add these permissions:
   - `openid`
   - `email`
   - `profile`
   - `User.Read`
6. Click **Add permissions**
7. Click **Grant admin consent for [Organization]**

## Step 5: Decide who may sign in (Enterprise application)

In **Enterprise applications** → your SSO app:

1. **Properties** → **Assignment required? = Yes**, **Visible to users? = No** → Save.
2. **Users and groups** → add the groups that should use Chronicle (IT, and any read-only readers).

Entra then refuses everyone else before they reach Chronicle. This is the main control over who gets in.

## Step 6: Configure FynBus Chronicle

From the app registration's **Overview** page take the **Application (client) ID** and the **Directory (tenant) ID**, then set in `web.env` (production: `/srv/docker/chronicle/env/web.env` on fbdocker01):

```env
SSO_ENABLED=True
SSO_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx     # the SSO app
SSO_CLIENT_SECRET=your-client-secret-value
MICROSOFT_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx  # tenant GUID, required
# Optional (defaults shown):
# SSO_ALLOWED_EMAIL_DOMAINS=fynbus.dk
# SSO_ALLOW_GUESTS=False
# SSO_AUTO_CREATE_USERS=True
```

- Chronicle **refuses to start** with `SSO_ENABLED=True` unless `MICROSOFT_TENANT_ID` is the tenant GUID. `common`, `organizations` or a domain name would let accounts from other organisations sign in.
- `SSO_CLIENT_ID` / `SSO_CLIENT_SECRET` fall back to `MICROSOFT_CLIENT_ID` / `MICROSOFT_CLIENT_SECRET` (the shared app used by Graph mail), but a separate SSO app is recommended.

### Who gets an account

- **Self sign-up is closed.** allauth's own pages (`/allauth/signup/`, `/allauth/login/`, password reset, …) all lead to Chronicle's login page.
- **Existing users:** the first Microsoft sign-in is linked to the active Chronicle user with the same e-mail address (only one may have it). From then on the Entra object id alone decides, so a later change of address doesn't move the login to someone else.
- **New people** (in an assigned group, but with no Chronicle user yet) get a user in the **Viewer** group: read-only. Staff promote them by removing them from Viewer in Django Admin. With `SSO_AUTO_CREATE_USERS=False`, staff must create the user first.
- **Refused:** guest accounts (`#EXT#`) unless `SSO_ALLOW_GUESTS=True`, and addresses outside `SSO_ALLOWED_EMAIL_DOMAINS`. The user sees a message on the login page; the reason is logged.

If using Docker:

```bash
# Restart with the new settings (production: redeploy the Portainer stack)
CHRONICLE_VERSION=<version> docker compose -f docker-compose.prod.yml up -d
```

## Step 6b: Microsoft sign-in only (optional)

Once SSO works, you can turn off passwords so that MFA, Conditional Access and disabling an account in Entra all apply to Chronicle:

1. Let everyone sign in with **Office 365** once. In Django Admin → **Users**, the **SSO** column shows *✓ Tilknyttet* for linked users; filter *Microsoft-login: Ikke tilknyttet* to see who is missing.
2. Pick one or two **break-glass** accounts: local superusers with long passwords kept in the password manager, for when Microsoft sign-in is unavailable.
3. Set in `web.env` and redeploy:

```env
SSO_ONLY=True
SSO_BREAK_GLASS_USERS=breakglass1,breakglass2
SESSION_MAX_HOURS=12   # recommended: a disabled user loses access by the next day
```

- The login page then shows only the Office 365 button. Break-glass accounts use `/accounts/login/?local=1`; every such login is logged as a warning and in the login log.
- Passwords are refused for everyone else, on Chronicle's login page, allauth's and the Django admin's. API keys are not affected.
- `SSO_ONLY=True` without `SSO_ENABLED=True` refuses to start; `manage.py check` warns (`accounts.W001`) if no break-glass account is named.
- Existing sessions run until they expire (`SESSION_MAX_HOURS`); the rule applies at the next login.

## Step 7: Configure Django Sites

1. Log into Django Admin (`/admin/`)
2. Go to **Sites**
3. Edit the default site:
   - **Domain name**: your-domain.dk
   - **Display name**: FynBus Chronicle

## Step 8: Test SSO

1. Log out if currently logged in
2. Go to `/accounts/login/`
3. Click **Office 365** button
4. You should be redirected to Microsoft login
5. After authentication, you'll be redirected back to Chronicle

## Troubleshooting

### Error: "AADSTS50011: Reply URL does not match"

**Cause**: Redirect URI mismatch

**Fix**:
1. In Azure Portal, verify the redirect URI exactly matches
2. Check for trailing slashes
3. Ensure HTTPS is used in production

### Error: "Application with identifier was not found"

**Cause**: Wrong client ID

**Fix**: Verify `MICROSOFT_CLIENT_ID` matches the Application ID in Azure

### Error: "Invalid client secret"

**Cause**: Client secret expired or incorrect

**Fix**:
1. Create a new client secret in Azure
2. Update `SSO_CLIENT_SECRET` in your configuration
3. Restart the application

### Users Can Log In But Can Only Read

**Cause**: A user created by SSO starts in the **Viewer** group (read-only).

**Fix**: In Django Admin → **Users**, remove the user from the **Viewer** group to make them an editor.

### "Din Microsoft-konto hører ikke til en tilladt organisation" / "Gæstekonti kan ikke logge ind"

**Cause**: The account's address is outside `SSO_ALLOWED_EMAIL_DOMAINS`, or it is a guest account.

**Fix**: Add the domain to `SSO_ALLOWED_EMAIL_DOMAINS`, or set `SSO_ALLOW_GUESTS=True` if guests should get in.

## Security Recommendations

### Restrict to Organization

Only users from your tenant can sign in: `MICROSOFT_TENANT_ID` must be your tenant GUID, and Chronicle won't start with SSO on otherwise.

### Group-Based Access

Use **Assignment required = Yes** on the enterprise application (Step 5) and assign only the groups that should use Chronicle. Entra enforces it, so nothing is needed in Chronicle.

### Secret Rotation

Set calendar reminders to rotate the client secret before expiration:

1. Create new secret in Azure (while old one still works)
2. Update `SSO_CLIENT_SECRET`
3. Verify SSO still works
4. Delete old secret in Azure

## Reference

### Azure Portal URLs

- App registrations: `https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade`
- Enterprise applications: `https://portal.azure.com/#view/Microsoft_AAD_IAM/StartboardApplicationsMenuBlade`

### Django Allauth Documentation

- [Microsoft Provider](https://docs.allauth.org/en/latest/socialaccount/providers/microsoft.html)

### Microsoft Documentation

- [Register an application](https://learn.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app)
- [OAuth 2.0 authorization code flow](https://learn.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-auth-code-flow)
