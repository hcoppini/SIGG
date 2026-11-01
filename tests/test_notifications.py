import unittest
import os
import shutil
from notifications import (
    load_settings, save_settings, push_in_app_notification,
    get_recent_in_app_notifications, dispatch_1635_preclose_alert,
    dispatch_1650_fixing_action_sheet
)

class TestNotifications(unittest.TestCase):
    def test_settings_save_and_load(self):
        saved = save_settings({"discord_webhook_url": "https://discord.com/api/webhooks/test/123", "sound_alerts_enabled": True})
        loaded = load_settings()
        self.assertEqual(loaded["discord_webhook_url"], "https://discord.com/api/webhooks/test/123")
        self.assertTrue(loaded["sound_alerts_enabled"])

    def test_in_app_notification_queue(self):
        push_in_app_notification("Test Alert", "Testing in-app queue", level="info")
        notifs = get_recent_in_app_notifications()
        self.assertGreater(len(notifs), 0)
        self.assertEqual(notifs[0]["title"], "Test Alert")

    def test_payload_builder_handles_empty(self):
        regime = {"regime": "GREEN", "status_label": "UNLOCKED", "action_msg": "Trade freely"}
        summary = {"active_positions_count": 0, "max_positions": 3, "cash": 20000.0, "vacant_slots": 3, "positions": []}
        candidates = [{"Ticker": "TPE.WA", "Close": 4.5, "Order_Shares": 1400, "Order_Limit_Price": 4.55, "Day_Gain_Pct": 4.5, "Volume_Surge": 2.1, "Runner_Score": 1.8}]
        
        # Dispatch with dummy invalid URL shouldn't crash python; it will return an error status dict gracefully
        res = dispatch_1635_preclose_alert(regime, summary, candidates, webhook_url="http://invalid.localhost:9999/test")
        self.assertEqual(res["status"], "error")

if __name__ == '__main__':
    unittest.main()
