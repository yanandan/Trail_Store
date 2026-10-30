import unittest
import io
import json
from unittest.mock import patch
from app import PRODUCTS, agent, graph, ai_plan


class AgentTests(unittest.TestCase):
    def test_rain_budget_and_stock(self):
        result = agent('hiking in rain under $150')
        self.assertTrue(result['products'])
        for p in result['products']:
            self.assertIn('hiking', p['activities'])
            self.assertIn('rain', p['weather'])
            self.assertLessEqual(p['price'], 150)
            self.assertGreater(p['stock'], 0)
            self.assertTrue(p['evidence'])

    def test_impossible_constraints_not_relaxed(self):
        self.assertEqual(agent('rainy hiking boots under $50')['products'], [])

    def test_category(self):
        self.assertTrue(all(p['category']=='Packs' for p in agent('hiking', 'Packs')['products']))

    def test_no_out_of_stock(self):
        self.assertNotIn('p10', [p['id'] for p in agent('running shoes under $200')['products']])

    def test_zero_budget(self):
        self.assertEqual(agent('hiking under $0')['products'], [])

    def test_graph_integrity(self):
        g=graph()
        ids={n['id'] for n in g['nodes']}
        self.assertEqual(len(ids), len(g['nodes']))
        self.assertTrue(all(e['source'] in ids and e['target'] in ids for e in g['edges']))
        self.assertEqual(sum(n['type']=='product' for n in g['nodes']), len(PRODUCTS))

    def test_ai_plan_validates_tool_arguments(self):
        plan = dict(activities=['hiking'], weather=['rain'], category='Footwear', budget=200)
        def response(data):
            return io.BytesIO(json.dumps({'choices': [{'message': {'tool_calls': [{'function': {'name': 'search_catalog', 'arguments': json.dumps(data)}}]}}]}).encode())
        with patch.dict('os.environ', {'TRAIL_AI_API_KEY': 'test-only'}):
            with patch('urllib.request.urlopen', return_value=response(plan)):
                self.assertEqual(ai_plan('wet trail boots'), plan)
            with patch('urllib.request.urlopen', return_value=response(dict(plan, category='Invented'))):
                with self.assertRaises(ValueError):
                    ai_plan('wet trail boots')

    def test_provider_failure_falls_back(self):
        with patch('app.ai_plan', side_effect=RuntimeError('provider unavailable')):
            result = agent('hiking under $150')
        self.assertTrue(result['products'])
        self.assertIn('unavailable', result['trace'][0]['detail'])
        self.assertIn('Local', result['mode'])


if __name__ == '__main__':
    unittest.main()
