import time
import logging
from pathlib import Path
from scripts.utils.email_notify import send_email
from scripts.streaming.credentials_manager import get_secret

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("EmailTest")

def run_tests():
    # Setup a dummy file to attach
    test_file = Path("scratch/test_attachment.txt")
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("This is a test attachment containing Dealer Levels.\nSPX: 5500 Call Wall\n")
    
    email_to = get_secret("email_to")
    if not email_to:
        log.error("No email_to found in secrets. Cannot run tests.")
        return

    # 1. Test HTML Support (blocking)
    log.info("--- Test 1: HTML Support ---")
    send_email(
        subject="🧪 Test 1: HTML Alert",
        body="<h1>Test Alert</h1><p>This is a <b style='color:green'>POSITIVE GAMMA</b> regime test.</p>",
        is_html=True,
        blocking=True
    )
    time.sleep(1)

    # 2. Test File Attachment + HTML (blocking)
    log.info("--- Test 2: File Attachment ---")
    send_email(
        subject="🧪 Test 2: Attachment Alert",
        body="Attached is the dealer levels text file.",
        file_paths=[str(test_file)],
        blocking=True
    )
    time.sleep(1)

    # 3. Test Multiple Recipients (blocking)
    # We will use the same email twice just to prove the list formatting works without spamming a random email.
    log.info("--- Test 3: Multiple Recipients ---")
    list_recipients = [email_to, email_to]
    send_email(
        subject="🧪 Test 3: List Recipients Alert",
        body="This email was sent to a list of recipients.",
        to_email=list_recipients,
        blocking=True
    )
    time.sleep(1)

    # 4. Test Async Fire-and-Forget
    log.info("--- Test 4: Async Fire-and-Forget ---")
    start = time.time()
    send_email(
        subject="🧪 Test 4: Async Alert",
        body="This email was fired in the background without blocking the main thread.",
        blocking=False
    )
    elapsed = time.time() - start
    log.info(f"Async call took {elapsed:.4f} seconds (should be near 0).")
    
    # Wait to let the background thread finish
    log.info("Waiting for background thread to complete...")
    time.sleep(5)
    log.info("All tests completed successfully!")

if __name__ == "__main__":
    run_tests()
