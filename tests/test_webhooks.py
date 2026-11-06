import json
import hmac
import hashlib


def test_meta_webhook_verification_handshake(client):
    # Valid verify token
    resp = client.get("/api/v1/webhooks/whatsapp?hub.mode=subscribe&hub.challenge=11582012&hub.verify_token=test_verify_token")
    assert resp.status_code == 200
    assert resp.text == "11582012"

    # Invalid verify token
    resp_bad = client.get("/api/v1/webhooks/whatsapp?hub.mode=subscribe&hub.challenge=11582012&hub.verify_token=wrong_token")
    assert resp_bad.status_code == 403


def test_meta_webhook_signature_rejection(client):
    payload = json.dumps({"entry": []}).encode("utf-8")
    headers = {"X-Hub-Signature-256": "sha256=invalid_hash_string"}

    resp = client.post("/api/v1/webhooks/whatsapp", content=payload, headers=headers)
    assert resp.status_code == 403


def test_meta_webhook_inbound_and_idempotency(client, mock_wa):
    """
    IDEMPOTENCY TEST:
    Verifies that when WhatsApp re-delivers the exact same webhook message event,
    the platform processes it once and ignores the duplicate!
    """
    message_payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "1001",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "contacts": [{"profile": {"name": "Test Webhook Patient"}}],
                    "messages": [{
                        "from": "919999900000",
                        "id": "wamid_unique_test_12345",
                        "timestamp": "1700000000",
                        "type": "text",
                        "text": {"body": "What are your consultation timings?"}
                    }]
                }
            }]
        }]
    }

    raw_bytes = json.dumps(message_payload).encode("utf-8")
    mac = hmac.new(b"test_meta_secret", raw_bytes, hashlib.sha256).hexdigest()
    headers = {"X-Hub-Signature-256": f"sha256={mac}"}

    # 1. First delivery
    resp1 = client.post("/api/v1/webhooks/whatsapp", content=raw_bytes, headers=headers)
    assert resp1.status_code == 200
    assert len(mock_wa.sent_messages) == 1
    assert "Mon-Sat" in mock_wa.sent_messages[0]["message"]

    # 2. Duplicate re-delivery (same message_id: wamid_unique_test_12345)
    resp2 = client.post("/api/v1/webhooks/whatsapp", content=raw_bytes, headers=headers)
    assert resp2.status_code == 200
    # Sent messages count should still remain 1 (no duplicate outbound response)
    assert len(mock_wa.sent_messages) == 1


def test_legacy_twilio_webhook(client, mock_wa):
    """Verifies that POST /webhook works seamlessly for Twilio form payloads."""
    form_data = {
        "From": "whatsapp:+919876543210",
        "Body": "What is the clinic address?",
        "ProfileName": "Twilio User",
        "MessageSid": "SM_legacy_test_123"
    }

    resp = client.post("/webhook", data=form_data)
    assert resp.status_code == 200
    assert resp.text == "OK"
    assert len(mock_wa.sent_messages) >= 1
    assert "Bangalore" in mock_wa.sent_messages[-1]["message"]
