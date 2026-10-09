import unittest

from skill_trigger_bench.similarity import cosine, similar_pairs, stem, tfidf_vectors, tokens


class SimilarityTests(unittest.TestCase):
    def test_stopwords_removed_and_stemmed(self):
        self.assertEqual(tokens("Use this when the user wants to convert PDFs"), ["convert", "pdf"])

    def test_stem_keeps_short_words(self):
        self.assertEqual(stem("bus"), "bus")
        self.assertEqual(stem("emails"), "email")
        self.assertEqual(stem("templates"), "template")
        self.assertEqual(stem("boxes"), "box")

    def test_identical_docs_score_one(self):
        a, b = tfidf_vectors(["merge pdf files", "merge pdf files"])
        self.assertAlmostEqual(cosine(a, b), 1.0, places=6)

    def test_unrelated_docs_score_zero(self):
        a, b = tfidf_vectors(["merge pdf files", "deploy kubernetes cluster"])
        self.assertEqual(cosine(a, b), 0.0)

    def test_pairs_sorted_and_thresholded(self):
        docs = ["send email with resend api", "resend email webhooks api", "bake sourdough bread"]
        pairs = similar_pairs(docs, 0.2)
        self.assertEqual([(i, j) for i, j, _, _ in pairs], [(0, 1)])
        self.assertIn("resend", pairs[0][3])
