import unittest
import json
from app import app
from catalyst_engine import analyze_headline_catalyst, get_ai_catalyst_intelligence, default_neutral_catalyst

class TestCatalystEngine(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_classify_catalyst_positive(self):
        title = "CD Projekt zanotował rekordowe zyski i przebił konsensus rynkowy"
        score, category, tag = analyze_headline_catalyst(title)
        self.assertIn("EARNINGS", category)
        self.assertGreater(score, 0)
        self.assertIsNotNone(tag)

    def test_classify_catalyst_negative(self):
        title = "Krwawy piątek na giełdzie. Wyprzedaż akcji, załamanie kursu i panika inwestorów"
        score, category, tag = analyze_headline_catalyst(title)
        self.assertIn("SELLOFF", category)
        self.assertLess(score, 0)
        self.assertIsNotNone(tag)

    def test_classify_contract_win(self):
        title = "Budimex podpisał nową umowę o wartości 500 mln zł"
        score, category, tag = analyze_headline_catalyst(title)
        self.assertIn("CONTRACT", category)
        self.assertGreater(score, 0)

    def test_default_neutral_catalyst(self):
        res = default_neutral_catalyst("TEST")
        self.assertEqual(res["symbol"], "TEST")
        self.assertEqual(res["ai_score"], 0.0)
        self.assertEqual(res["catalyst_tag"], "⚡ TECHNICAL MOMENTUM")

    def test_api_news_catalysts_endpoint(self):
        res = self.client.get('/api/news/catalysts')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data.get("status"), "success")
        self.assertIn("count", data)
        self.assertIn("high_impact", data)
        self.assertIn("articles", data)

    def test_api_news_catalysts_with_symbols(self):
        res = self.client.get('/api/news/catalysts?symbols=KGHM,ALLEGRO')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data.get("status"), "success")
        self.assertIn("ticker_analysis", data)

if __name__ == '__main__':
    unittest.main()
