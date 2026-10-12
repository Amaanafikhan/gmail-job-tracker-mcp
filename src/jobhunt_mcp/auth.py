"""One-time Gmail sign-in: `jobhunt-auth`. Opens a browser for Google's read-only consent screen."""

from __future__ import annotations

from .mail import GmailMail


def main() -> None:
    try:
        email = GmailMail().sign_in()
    except ImportError:
        raise SystemExit('Gmail support is not installed. Run: pip install -e ".[gmail]"')
    except RuntimeError as e:
        raise SystemExit(str(e))
    print(f"Signed in as {email} (read-only). Token saved; you can now use JOBHUNT_MAIL=gmail.")


if __name__ == "__main__":
    main()
