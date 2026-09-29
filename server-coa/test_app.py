import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app


class CoaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'private').mkdir()
        self.pdf = b'%PDF-1.7\noriginal fixture'
        self.sha = hashlib.sha256(self.pdf).hexdigest()
        self.path = self.root / 'private' / (self.sha + '.pdf')
        self.path.write_bytes(self.pdf)
        record = dict(sha256=self.sha, code='EX-CM510-05A', lot='260611',
                      filename='COA-EX-CM510-05A-260611.pdf', size=len(self.pdf), verified=True)
        (self.root / 'catalog.json').write_text(json.dumps([record]))
        self.client = create_app(self.root, 's' * 64).test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def link(self):
        return self.client.get('/lookup?q=260611').json['results'][0]['download'].replace('/api/coa', '')

    def test_exact_and_normalized_search(self):
        for q in ['260611', 'EX-CM510-05A', 'ex cm510 05a', 'EX-CM510-05A-260611']:
            self.assertEqual(self.client.get('/lookup', query_string={'q': q}).json['count'], 1)
        for q in ['260', '000000', 'CM510']:
            self.assertEqual(self.client.get('/lookup', query_string={'q': q}).json['count'], 0)

    def test_invalid_and_empty(self):
        for q in ['', '---', 'a' * 81, '../catalog.json', "' OR 1=1", '<script>']:
            self.assertEqual(self.client.get('/lookup', query_string={'q': q}).status_code, 400)

    def test_original_and_no_cache(self):
        response = self.client.get(self.link())
        self.assertEqual(response.data, self.pdf)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertIn('attachment;', response.headers['Content-Disposition'])

    def test_invalid_expired_and_future_signature(self):
        link = self.link()
        self.assertEqual(self.client.get(link + 'x').status_code, 403)
        with patch('app.time.time', return_value=time.time() + 601):
            self.assertEqual(self.client.get(link).status_code, 403)
        self.assertEqual(self.client.get('/download/' + self.sha).status_code, 403)
        self.assertEqual(self.client.get('/download/' + self.sha + '?expires=abc').status_code, 403)
        self.assertEqual(self.client.get('/download/' + self.sha, query_string={'expires':int(time.time())+60, 'signature':'\uac00'}).status_code, 403)

    def test_corrupted_or_missing_file(self):
        link = self.link()
        self.path.write_bytes(b'changed')
        self.assertEqual(self.client.get(link).status_code, 503)
        self.path.unlink()
        self.assertEqual(self.client.get(link).status_code, 503)

    def test_no_private_routes(self):
        for path in ['/catalog.json', '/private/' + self.sha + '.pdf', '/admin', '/']:
            self.assertEqual(self.client.get(path).status_code, 404)


if __name__ == '__main__':
    unittest.main()
