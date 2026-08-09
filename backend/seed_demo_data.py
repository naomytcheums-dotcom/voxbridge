"""Seeds the call log with a few realistic sample calls so the dashboard
has something to show before a real phone line is connected.

Not part of the app itself — a one-off dev utility. Safe to delete once
real calls start coming in.
"""
import time

from app.call_log import CallLog
from app.config import get_settings

settings = get_settings()
log = CallLog(settings.call_log_db_path)

calls = [
    {
        "caller_number": "+237670123456",
        "duration_s": 96,
        "latency_ms": 480,
        "turns": [
            ("caller", "Hi, do you have any red bags?"),
            ("assistant", "Yes, we have a leather tote bag in red, twenty five thousand francs, four in stock."),
            ("caller", "Do you have anything cheaper in red?"),
            ("assistant", "We also have a canvas crossbody bag in red, but it's currently out of stock. Would you like the leather tote instead?"),
            ("caller", "Yes, I'll take the leather tote."),
            ("assistant", "Great — can I get your name and phone number to place the order?"),
            ("caller", "Aline Mballa, zero six seven zero one two three four five six."),
            ("assistant", "Got it, Aline. I've created an order for one leather tote bag in red — our team will confirm with you shortly."),
        ],
    },
    {
        "caller_number": "+237699887766",
        "duration_s": 41,
        "latency_ms": 610,
        "turns": [
            ("caller", "What sneakers do you have under twenty thousand?"),
            ("assistant", "We have classic sneakers in white or black, both eighteen thousand francs."),
            ("caller", "Do you deliver to Yaounde?"),
            ("assistant", "That's outside what I can confirm right now — let me get you a human on the team."),
        ],
    },
    {
        "caller_number": "+237655443322",
        "duration_s": 58,
        "latency_ms": 390,
        "turns": [
            ("caller", "Hello, are you open on Sundays?"),
            ("assistant", "Yes, we're open every day. Is there anything I can help you find?"),
            ("caller", "Just checking, thanks."),
            ("assistant", "You're welcome — have a great day."),
        ],
    },
]

now = time.time()
first_call_id = None
for i, call in enumerate(calls):
    call_id = log.start_call(call["caller_number"])
    if i == 0:
        first_call_id = call_id
    for role, text in call["turns"]:
        log.log_turn(call_id, role, text)
    log.log_first_audio_latency(call_id, call["latency_ms"])
    log.end_call(call_id)

log.create_order(
    call_id=first_call_id,
    product_id="bag-001",
    quantity=1,
    customer_name="Aline Mballa",
    customer_phone="+237670123456",
)

print(f"Seeded {len(calls)} demo calls and 1 order into {settings.call_log_db_path}")
