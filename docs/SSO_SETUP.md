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

- **Name**: FynBus Chronicle
- **Supported account types**: Accounts in this organizational directory only (Single tenant)
- **Redirect URI**:
  - Type: Web
  - URL: `https://your-domain.dk/accounts/microsoft/login/callback/`

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
4. Choose expiration (recommend 24 months)
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

## Step 5: Get Application IDs

From your app registration's **Overview** page, note:

- **Application (client) ID**: This is `MICROSOFT_CLIENT_ID`
- **Directory (tenant) ID**: This is `MICROSOFT_TENANT_ID`

## Step 6: Configure FynBus Chronicle

Update your `.env` file:

```env
SSO_ENABLED=True
MICROSOFT_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
MICROSOFT_CLIENT_SECRET=your-client-secret-value
MICROSOFT_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

If using Docker:

```bash
# Rebuild and restart
docker compose -f docker-compose.prod.yml up -d --build
```

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
2. Update `MICROSOFT_CLIENT_SECRET` in your configuration
3. Restart the application

### Users Can Log In But Don't Have Access

**Cause**: User was created but needs staff/admin permissions

**Fix**:
1. Log into Django Admin with a superuser
2. Go to **Users**
3. Find the user and grant appropriate permissions

## Security Recommendations

### Restrict to Organization

The default configuration only allows users from your Azure AD tenant. This is enforced by setting `MICROSOFT_TENANT_ID` to your organization's tenant ID.

### Group-Based Access (Advanced)

To restrict access to specific groups:

1. In Azure, add a **Groups claim** in Token configuration
2. In Django, create custom authentication backend to check group membership

### Secret Rotation

Set calendar reminders to rotate the client secret before expiration:

1. Create new secret in Azure (while old one still works)
2. Update `MICROSOFT_CLIENT_SECRET`
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
