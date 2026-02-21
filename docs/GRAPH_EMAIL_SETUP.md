# Microsoft Graph Email Setup Guide

This guide covers configuring FynBus Chronicle to send emails via the Microsoft Graph API instead of SMTP.

## Why Graph API?

- Works with M365 tenants that have disabled SMTP AUTH
- No SMTP credentials to manage
- The logged-in user appears as the email sender
- Reuses the existing Azure AD app registration (from SSO setup)

## Prerequisites

- Azure AD app registration (see [SSO Setup](SSO_SETUP.md) if not already configured)
- Azure AD admin access to grant application permissions
- A valid M365 mailbox for the sender address

## Step 1: Add Mail.Send Permission

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Microsoft Entra ID** > **App registrations**
3. Select your FynBus Chronicle app
4. Go to **API permissions** > **Add a permission**
5. Select **Microsoft Graph**
6. Select **Application permissions** (not Delegated)
7. Search for and add: `Mail.Send`
8. Click **Add permissions**
9. Click **Grant admin consent for [Organization]**

> **Important**: Use *Application* permissions (not *Delegated*) since email is sent server-side via client credentials flow.

## Step 2: Configure Environment

Add to your `.env` or `.env.prod`:

```env
EMAIL_USE_GRAPH=True
```

The Graph backend reuses these existing settings (from SSO):

```env
MICROSOFT_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
MICROSOFT_CLIENT_SECRET=your-client-secret-value
MICROSOFT_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

These email settings are still used:

```env
DEFAULT_FROM_EMAIL=it@fynbus.dk
CHRONICLE_EMAIL_RECIPIENTS=manager@fynbus.dk,team@fynbus.dk
```

If using Docker, add to your docker-compose environment:

```yaml
- EMAIL_USE_GRAPH=${EMAIL_USE_GRAPH:-False}
```

## Step 3: Verify

### Quick test via Django shell

```bash
python manage.py shell
```

```python
from django.core.mail import send_mail

send_mail(
    subject="Test from Chronicle",
    message="Graph email backend works!",
    from_email="it@fynbus.dk",
    recipient_list=["your-email@fynbus.dk"],
)
```

A successful send returns `1` with no exceptions.

### Check logs

The backend logs all send attempts:

```
INFO Email sent via Graph API from=it@fynbus.dk to=['recipient@fynbus.dk'] subject='...'
```

## Troubleshooting

### 403 Forbidden

**Cause**: Missing or unapproved `Mail.Send` permission.

**Fix**:
1. Verify `Mail.Send` is listed under API permissions
2. Ensure admin consent has been granted (green checkmark)
3. Wait a few minutes for permission propagation

### 404 Not Found

**Cause**: The `from_email` address is not a valid mailbox in the tenant.

**Fix**: Ensure `DEFAULT_FROM_EMAIL` (or the logged-in user's email) corresponds to a real M365 mailbox.

### Token acquisition failure

**Cause**: Invalid client credentials.

**Fix**:
1. Verify `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, and `MICROSOFT_TENANT_ID` are correct
2. Check if the client secret has expired
3. Create a new secret if needed (see [SSO Setup](SSO_SETUP.md#step-3-create-client-secret))

### Emails sent but not appearing

**Cause**: The email may be in the recipient's junk/spam folder.

**Fix**:
1. Check spam/junk folders
2. Add the sender address to the organization's safe senders list
3. Verify SPF/DKIM/DMARC records for your domain

## Security Considerations

### Principle of Least Privilege

The `Mail.Send` application permission allows the app to send email as *any* user in the tenant. To restrict this:

1. In Azure Portal, go to **Enterprise applications** > select your app
2. Under **Properties**, set **Assignment required** to Yes
3. Use [Application Access Policies](https://learn.microsoft.com/en-us/graph/auth-limit-mailbox-access) to restrict which mailboxes the app can send from

### Secret Rotation

The same client secret is used for SSO and Graph email. When rotating secrets:

1. Create a new secret in Azure (while the old one still works)
2. Update `MICROSOFT_CLIENT_SECRET` in your environment
3. Restart the application
4. Verify both SSO and email still work
5. Delete the old secret in Azure

## Fallback to SMTP

To switch back to SMTP, set:

```env
EMAIL_USE_GRAPH=False
```

The SMTP settings (`EMAIL_HOST`, `EMAIL_PORT`, etc.) are preserved and will be used automatically.

## Reference

- [Microsoft Graph sendMail API](https://learn.microsoft.com/en-us/graph/api/user-sendmail)
- [Application permissions overview](https://learn.microsoft.com/en-us/graph/permissions-overview#application-permissions)
- [Limit application permissions to specific mailboxes](https://learn.microsoft.com/en-us/graph/auth-limit-mailbox-access)
