import logging
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings

logger = logging.getLogger("panchayat.email")


def _send_email(to_email: str, subject: str, body: str, dev_label: str = "EMAIL") -> bool:
    """
    Shared low-level sender.

    Production on Render Free uses the Resend HTTPS API instead of SMTP,
    because Render Free blocks outbound SMTP ports.
    Local development can still fall back to SMTP when Resend is not configured.
    """
    # Production/Render Free: send through Resend HTTPS API.
    if settings.RESEND_API_KEY and settings.RESEND_FROM_EMAIL:
        try:
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": settings.RESEND_FROM_EMAIL,
                    "to": [to_email],
                    "subject": subject,
                    "text": body,
                },
                timeout=15.0,
            )

            if 200 <= response.status_code < 300:
                return True

            logger.error(
                "Resend rejected email to %s: HTTP %s",
                to_email,
                response.status_code,
            )
            return False

        except Exception:
            logger.exception("Failed to send email to %s through Resend", to_email)
            return False

    # Local-development SMTP fallback.
    if not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD):
        logger.warning(
            "No email provider configured - printing email to console instead.\n"
            "  To: %s\n"
            "  Subject: %s",
            to_email,
            subject,
        )
        print(
            f"\n[DEV MODE - {dev_label} NOT SENT] "
            f"To: {to_email} | Subject: {subject}\n{body}\n"
        )
        return True

    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=15,
        ) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            refused = server.sendmail(
                settings.SMTP_USER,
                [to_email],
                msg.as_string(),
            )

        if refused:
            logger.error(
                "SMTP server refused the recipient %s: %s",
                to_email,
                refused,
            )
            return False

        return True

    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False


def send_otp_email(to_email: str, code: str, purpose: str) -> bool:
    """Sends a one-time code for registration verification, password reset, or account deletion."""
    purpose_text = {
        "register": ("complete your registration", "Your JanSeva Connect verification code"),
        "password_reset": ("reset your password", "Your JanSeva Connect password reset code"),
        "delete_account": ("permanently delete your account", "Confirm account deletion - JanSeva Connect"),
        "change_password": ("change your password", "Your JanSeva Connect password change code"),
        "admin_create_user": ("verify this email for a new account", "Verify email - JanSeva Connect"),
    }
    verb, subject = purpose_text.get(purpose, ("sign in", "Your JanSeva Connect login code"))
    body = (
        f"Your one-time code to {verb} is:\n\n"
        f"    {code}\n\n"
        f"This code expires in {settings.OTP_EXPIRY_MINUTES} minutes. "
        f"If you did not request this, you can safely ignore this email."
    )
    return _send_email(to_email, subject, body, dev_label="OTP")


def send_account_created_email(to_email: str, full_name: str, role: str) -> bool:
    """Confirm provisioning without ever transmitting a password by email."""
    subject = "Your JanSeva Connect account has been created"
    body = (
        f"Hello {full_name},\n\n"
        f"An account has been created for you on the JanSeva Connect Smart Community Management Platform "
        f"with the role of {role}.\n\n"
        f"Login email: {to_email}\n\n"
        "Your administrator will provide the temporary password through an approved secure channel. "
        "Change it immediately after your first sign-in.\n"
    )
    return _send_email(to_email, subject, body, dev_label="ACCOUNT CREATED EMAIL")


def send_role_change_email(to_email: str, full_name: str, old_label: str, new_label: str) -> bool:
    """Sent whenever an admin reassigns a staff/admin account's role or
    jurisdiction, so the officer hears about a promotion, demotion, or
    transfer directly from the platform rather than discovering it only
    when their own access changes."""
    subject = "Your JanSeva Connect role has been updated"
    body = (
        f"Hello {full_name},\n\n"
        f"Your role on the JanSeva Connect portal has just been updated by an administrator.\n\n"
        f"Previous role: {old_label}\n"
        f"New role: {new_label}\n\n"
        f"If this change is unexpected, please contact your administrator.\n"
    )
    return _send_email(to_email, subject, body, dev_label="ROLE CHANGE EMAIL")


def send_certificate_issued_email(to_email: str, full_name: str, certificate_type: str, certificate_number: str) -> bool:
    subject = f"Your {certificate_type} certificate has been issued"
    body = (
        f"Hello {full_name},\n\n"
        f"Your {certificate_type} certificate (No. {certificate_number}) has been issued and is ready "
        f"to download from the JanSeva Connect portal under Certificates.\n"
    )
    return _send_email(to_email, subject, body, dev_label="CERTIFICATE EMAIL")


def send_application_status_email(to_email: str, full_name: str, scheme_name: str, status: str, remarks: str = None) -> bool:
    if status == "approved":
        subject = f"Your application for {scheme_name} has been approved"
        # An approval can carry instructions - "collect the order at the mandal
        # office on Tuesday", "bring the original Aadhaar". This branch used to
        # drop remarks entirely, so anything the officer wrote on an approval
        # was visible only to someone who went looking in the portal.
        note = f"\n\nNote from the reviewing officer:\n{remarks.strip()}\n" if (remarks or "").strip() else ""
        body = (
            f"Hello {full_name},\n\n"
            f"Good news - your application for \"{scheme_name}\" has been APPROVED."
            f"{note}\n"
            f"You can download an approval confirmation from the JanSeva Connect portal under My Applications.\n"
        )
    elif status == "rejected":
        subject = f"Update on your application for {scheme_name}"
        reason = f"\n\nReason given: {remarks}" if remarks else ""
        body = (
            f"Hello {full_name},\n\n"
            f"Your application for \"{scheme_name}\" was not approved this time.{reason}\n\n"
            f"You're welcome to review the requirements and apply again from the JanSeva Connect portal.\n"
        )
    else:
        subject = f"Update on your application for {scheme_name}"
        body = f"Hello {full_name},\n\nYour application for \"{scheme_name}\" is now marked as: {status}.\n"
    return _send_email(to_email, subject, body, dev_label="APPLICATION STATUS EMAIL")


def send_application_received_email(to_email: str, full_name: str, scheme_name: str) -> bool:
    return _send_email(
        to_email,
        f"Application received: {scheme_name}",
        (
            f"Hello {full_name},\n\nWe have received your application for \"{scheme_name}\". "
            "You can follow each review step in the JanSeva Connect portal under My Applications."
        ),
        dev_label="APPLICATION RECEIVED EMAIL",
    )


def send_certificate_request_received_email(to_email: str, full_name: str, certificate_type: str) -> bool:
    return _send_email(
        to_email,
        f"Certificate request received: {certificate_type}",
        (
            f"Hello {full_name},\n\nWe have received your request for a {certificate_type} certificate. "
            "The Panchayat office will review it and update you in the portal and by email."
        ),
        dev_label="CERTIFICATE REQUEST RECEIVED EMAIL",
    )


def send_certificate_request_status_email(to_email: str, full_name: str, certificate_type: str, status: str, remarks: str = None) -> bool:
    if status == "approved":
        subject = f"Your {certificate_type} certificate request is approved"
        # Same reason as the application approval above: an officer's note on
        # an approval is often the actionable part, and was being discarded.
        note = f"\n\nNote from the reviewing officer:\n{remarks.strip()}\n" if (remarks or "").strip() else ""
        body = (
            f"Hello {full_name},\n\nYour {certificate_type} certificate request has been approved."
            f"{note}\n"
            "The certificate will be issued shortly and you will receive another email when it is ready."
        )
    else:
        subject = f"Update on your {certificate_type} certificate request"
        reason = f"\n\nReason given: {remarks}" if remarks else ""
        body = f"Hello {full_name},\n\nYour {certificate_type} certificate request was not approved this time.{reason}\n\nYou may correct the details and submit a new request in the portal."
    return _send_email(to_email, subject, body, dev_label="CERTIFICATE REQUEST STATUS EMAIL")


def send_new_message_email(to_email: str, full_name: str, preview: str) -> bool:
    subject = "New message from JanSeva Connect"
    body = (
        f"Hello {full_name},\n\n"
        f"You have a new message from the Panchayat office:\n\n\"{preview}\"\n\n"
        f"Reply from the JanSeva Connect portal's chat section.\n"
    )
    return _send_email(to_email, subject, body, dev_label="CHAT MESSAGE EMAIL")


def send_welcome_email(to_email: str, full_name: str) -> bool:
    """Sent once, after a self-registered citizen verifies their email.

    Until now the only mail a self-registering citizen ever received was the
    OTP itself. That leaves no durable record that an account now exists
    against their address - which matters when the account was created by
    someone who mistyped their own email, or by someone else entirely.
    """
    subject = "Your JanSeva Connect account is ready"
    body = (
        f"Hello {full_name},\n\n"
        "Your JanSeva Connect citizen account has been created and your email address is verified.\n\n"
        f"Sign-in email: {to_email}\n\n"
        "Next step: complete your household profile from the dashboard. Until it is saved you "
        "cannot apply for schemes, request certificates, or raise a local issue - the office "
        "needs your village and mandal to route anything to the right place.\n\n"
        "If you did not create this account, contact your Panchayat office immediately and do "
        "not share your password or any verification code with anyone.\n"
    )
    return _send_email(to_email, subject, body, dev_label="WELCOME EMAIL")


def send_new_signin_email(to_email: str, full_name: str, when: str, ip_address: str | None, device: str | None) -> bool:
    """Security alert for a sign-in from a device/network not seen before.

    Deliberately NOT sent on every single sign-in. A district clerk signing in
    each morning would get a mail a day, learn to delete them unread, and miss
    the one that actually matters - the whole point of the alert. See
    app/utils/signin_alerts.py for how "not seen before" is decided.
    """
    subject = "New sign-in to your JanSeva Connect account"
    body = (
        f"Hello {full_name},\n\n"
        "Your JanSeva Connect account was just signed in to from a device or network we have "
        "not seen before.\n\n"
        f"  When:   {when}\n"
        f"  From:   {ip_address or 'unknown network'}\n"
        f"  Device: {device or 'unknown device'}\n\n"
        "If this was you, no action is needed.\n\n"
        "If it was NOT you, change your password immediately from the portal (Profile -> Change "
        "password) and tell your Panchayat office. Changing your password signs out every other "
        "session straight away.\n\n"
        "JanSeva Connect staff will never ask you for your password or a verification code.\n"
    )
    return _send_email(to_email, subject, body, dev_label="NEW SIGN-IN ALERT")


def send_team_message_email(to_email: str, full_name: str, sender_name: str, channel_label: str, preview: str) -> bool:
    """Notifies an officer of a message posted to a team chat channel they can see."""
    subject = f"New team chat message in {channel_label}"
    body = (
        f"Hello {full_name},\n\n"
        f"{sender_name} posted in the {channel_label} team chat:\n\n"
        f"\"{preview}\"\n\n"
        "Open the Chat section of JanSeva Connect to read the full conversation and reply.\n"
    )
    return _send_email(to_email, subject, body, dev_label="TEAM CHAT EMAIL")


def send_issue_reply_email(to_email: str, full_name: str, issue_title: str, status: str, reply: str) -> bool:
    """The office's answer on a local issue, including what they actually said."""
    subject = f"Update on your issue: {issue_title}"
    readable_status = {
        "open": "reopened", "in_progress": "in progress", "resolved": "marked resolved",
    }.get(status, status.replace("_", " "))
    body = (
        f"Hello {full_name},\n\n"
        f"Your reported issue \"{issue_title}\" is now {readable_status}.\n\n"
        f"Reply from the office:\n{reply.strip()}\n\n"
        "If this is marked resolved, please confirm or reject it in the portal under Local "
        "Issues, so the office knows whether the fix actually landed.\n"
    )
    return _send_email(to_email, subject, body, dev_label="ISSUE REPLY EMAIL")


def send_document_rejected_email(to_email: str, full_name: str, document_name: str, remarks: str | None) -> bool:
    """Tells a citizen a specific uploaded document was not accepted.

    Without this the rejection was silent: the application stayed open,
    waiting on a person who had no way of knowing. Only the one document
    needs re-uploading - the rest of the application is untouched.
    """
    subject = f"Please re-upload your {document_name}"
    reason = f"\n\nReason given by the office:\n{remarks.strip()}\n" if (remarks or "").strip() else "\n"
    body = (
        f"Hello {full_name},\n\n"
        f"The office could not accept the \"{document_name}\" you uploaded for your scheme "
        f"application.{reason}\n"
        "Please sign in to JanSeva Connect, open My Applications, and use \"Manage documents\" to "
        "upload that one document again. Nothing else about your application changes, and you do "
        "not need to apply again.\n"
    )
    return _send_email(to_email, subject, body, dev_label="DOCUMENT REJECTED EMAIL")


def send_issue_received_email(to_email: str, full_name: str, category: str, title: str) -> bool:
    """Acknowledges an issue the citizen just reported.

    Applying for a scheme and requesting a certificate both acknowledged
    themselves by email; reporting a problem did not, so the one action whose
    whole point is "somebody please notice this" was the one that gave back
    no proof it had been received.
    """
    desk = {
        "civic": ("local issue", "Your local office aims to reply within 7 days."),
        "application": (
            "service problem",
            "The service team can see this and will reply in the portal and by email.",
        ),
        "portal": (
            "portal problem",
            "The administrators who maintain the platform can see this and will follow up.",
        ),
    }.get(category, ("issue", "The office will review it and reply."))
    label, promise = desk

    subject = f"We received your {label}: {title}"
    body = (
        f"Hello {full_name},\n\n"
        f"Your {label} has been recorded:\n\n"
        f"    {title}\n\n"
        f"{promise}\n\n"
        "You can follow it, and reply once the office responds, under Local Issues in the "
        "JanSeva Connect portal.\n"
    )
    return _send_email(to_email, subject, body, dev_label="ISSUE RECEIVED EMAIL")
