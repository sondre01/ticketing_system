import os
import imaplib
import email
import email.message
from email.header import decode_header
import logging
from backend.database import get_db_cursor
from backend.config import GMAIL_IMAP_HOST, GMAIL_IMAP_PORT, GMAIL_USER, GMAIL_APP_PASSWORD

logger = logging.getLogger("ticketing_system.email_service")

def decode_mime_words(header_value: str | None) -> str:
    """Decodes MIME encoded header strings (e.g. =?utf-8?B?...?=)."""
    if not header_value:
        return ""
    decoded_fragments = decode_header(header_value)
    result = []
    for fragment, charset in decoded_fragments:
        if isinstance(fragment, bytes):
            try:
                result.append(fragment.decode(charset or "utf-8", errors="replace"))
            except Exception:
                result.append(fragment.decode("latin-1", errors="replace"))
        else:
            result.append(str(fragment))
    return "".join(result).strip()

def extract_email_body(msg: email.message.Message) -> str:
    """Extracts plain text body or fallback HTML from an email message."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            
            # Skip attachments
            if "attachment" in content_disposition:
                continue
                
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        return payload.decode(charset, errors="replace")
                    except Exception:
                        return payload.decode("latin-1", errors="replace")
            elif content_type == "text/html" and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body = payload.decode(charset, errors="replace")
                    except Exception:
                        body = payload.decode("latin-1", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                body = payload.decode(charset, errors="replace")
            except Exception:
                body = payload.decode("latin-1", errors="replace")

    return body.strip()

def generate_ticket_code_helper(cur) -> str:
    cur.execute("SELECT MAX(id) as max_id FROM ticketing_system.tickets;")
    res = cur.fetchone()
    next_id = (res["max_id"] or 0) + 1
    return f"KT-{1000 + next_id}"

def sync_gmail_tickets(limit: int = 15, mark_as_read: bool = False) -> dict:
    """
    Connects to Gmail via IMAP, fetches recent unread emails, and converts them to tickets.
    Deduplicates using email Message-ID in PostgreSQL.
    """
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        return {
            "success": False,
            "synced_count": 0,
            "message": "GMAIL_APP_PASSWORD is not set in .env. Please configure your 16-character Google App Password to enable email ingestion."
        }

    try:
        # 1. Connect to Gmail IMAP server over SSL
        mail = imaplib.IMAP4_SSL(GMAIL_IMAP_HOST, GMAIL_IMAP_PORT)
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        mail.select("INBOX")
        
        # 2. Search for UNSEEN (unread) messages
        status, search_data = mail.search(None, "UNSEEN")
        if status != "OK" or not search_data or not search_data[0]:
            mail.logout()
            return {
                "success": True,
                "synced_count": 0,
                "message": "No new unread emails found in Gmail inbox."
            }

        all_mail_ids = search_data[0].split()
        # Process the newest emails up to the specified limit
        mail_ids = all_mail_ids[-limit:] if len(all_mail_ids) > limit else all_mail_ids
        mail_ids.reverse()
        synced_tickets = []

        with get_db_cursor(commit=True) as cur:
            for m_id in mail_ids:
                res, data = mail.fetch(m_id, "(RFC822)")
                if res != "OK":
                    continue
                
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Extract Message-ID
                msg_id = msg.get("Message-ID", "").strip()
                if msg_id:
                    # Check if ticket already exists
                    cur.execute("SELECT id FROM ticketing_system.tickets WHERE email_message_id = %s;", (msg_id,))
                    if cur.fetchone():
                        logger.info(f"Skipping already ingested email: {msg_id}")
                        continue

                # Extract sender info
                from_header = decode_mime_words(msg.get("From", ""))
                from_name, from_email = email.utils.parseaddr(from_header)
                if not from_email:
                    from_email = from_header or "unknown@sender.com"
                if not from_name:
                    from_name = from_email

                # Extract subject and body
                subject = decode_mime_words(msg.get("Subject", "No Subject"))
                body = extract_email_body(msg)
                if not body:
                    body = "(No message content provided in email body)"

                # Check if sender has an existing account in the system
                cur.execute("SELECT id FROM ticketing_system.users WHERE email = %s;", (from_email.lower(),))
                matched_user = cur.fetchone()
                req_id = matched_user["id"] if matched_user else None

                # Generate code and insert ticket
                ticket_code = generate_ticket_code_helper(cur)
                cur.execute(
                    """
                    INSERT INTO ticketing_system.tickets
                    (ticket_code, title, description, requester_email, requester_name, requester_id, source, status, priority, email_message_id)
                    VALUES (%s, %s, %s, %s, %s, %s, 'email', 'open', 'medium', %s)
                    RETURNING id, ticket_code, title, requester_email, requester_id, created_at;
                    """,
                    (ticket_code, subject, body, from_email.lower(), from_name, req_id, msg_id or None)
                )
                new_ticket = cur.fetchone()
                if new_ticket.get("created_at"):
                    new_ticket["created_at"] = new_ticket["created_at"].isoformat()
                synced_tickets.append(new_ticket)
                logger.info(f"Created ticket {ticket_code} from email: {subject}")

                # Optionally mark email as read in Gmail
                if mark_as_read:
                    mail.store(m_id, "+FLAGS", "\\Seen")

        mail.logout()
        return {
            "success": True,
            "synced_count": len(synced_tickets),
            "tickets": synced_tickets,
            "message": f"Successfully ingested {len(synced_tickets)} new ticket(s) from Gmail."
        }

    except imaplib.IMAP4.error as imap_err:
        logger.error(f"Gmail IMAP authentication/protocol error: {imap_err}")
        return {
            "success": False,
            "synced_count": 0,
            "message": f"Gmail IMAP error: {imap_err}. Please ensure 2FA and an App Password are used."
        }
    except Exception as e:
        logger.error(f"Failed to sync emails from Gmail: {e}")
        return {
            "success": False,
            "synced_count": 0,
            "message": f"Failed to sync emails: {str(e)}"
        }
