import unittest

from backend.tools import generate_synthetic_embedding as synthetic


class SyntheticEmbeddingTests(unittest.TestCase):
    def test_deterministic_counts_and_fact_isolation(self):
        data, metadata = synthetic.generate(seed=20261027)
        self.assertEqual((data, metadata), synthetic.generate(seed=20261027))
        self.assertEqual(len(data['train']), 1200)
        scopes = []
        queries = []
        documents = []
        for split in ['train', 'dev', 'test']:
            scopes.append(set(metadata['teams'][split]))
            queries.append({r['query'] for r in data[split]})
            documents.append({r['positive'] for r in data[split]})
            self.assertEqual(len(queries[-1]), len(data[split]))
            if split != 'train':
                corpus = data[split+'_corpus']
                self.assertEqual(len(data[split]), 100)
                self.assertEqual(len(corpus), 1000)
                self.assertEqual(len(set(corpus)), 1000)
                self.assertTrue(documents[-1] <= set(corpus))
                self.assertEqual(len({fact['id'] for fact in metadata['facts'][split]}), 1000)
        for i in range(3):
            for j in range(i):
                self.assertFalse(scopes[i] & scopes[j])
                self.assertFalse(queries[i] & queries[j])
                self.assertFalse(documents[i] & documents[j])
        self.assertEqual(set(metadata['query_templates']['train']) & set(metadata['query_templates']['test']), set())

    def test_labels_match_unique_team_environment_and_topic(self):
        data, metadata = synthetic.generate(seed=20261027)
        for split in ['dev','test']:
            facts = metadata['facts'][split]
            keys = [(f['team'], f['environment'], f['topic']) for f in facts]
            self.assertEqual(len(set(keys)), 1000)
            by_doc = {f['document']: f for f in facts}
            for pair in data[split]:
                fact = by_doc[pair['positive']]
                self.assertIn(fact['city'], pair['query'])
                self.assertIn(fact['team'], pair['positive'])
                self.assertNotIn(fact['id'], pair['query'])
