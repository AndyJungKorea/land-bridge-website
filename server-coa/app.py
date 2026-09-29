"""Isolated Land Bridge COA lookup. Original PDFs are never web-root assets."""
import hashlib
import hmac
import io
import json
import os
import re
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_file


def normalize(value):
    return re.sub(r'[\s\-]', '', value).upper()


def create_app(data_dir=None, secret=None):
    app = Flask(__name__)
    root = Path(data_dir or os.environ['COA_DATA'])
    key = secret or os.environ['COA_SECRET']
    if len(key) < 32:
        raise ValueError('COA_SECRET must be at least 32 characters')
    records = json.loads((root / 'catalog.json').read_text(encoding='utf-8'))
    documents = {r['sha256']: r for r in records}
    if len(documents) != len(records):
        raise ValueError('Duplicate document identity')
    if len({(normalize(r['code']), normalize(r['lot'])) for r in records}) != len(records):
        raise ValueError('Conflicting product/lot revisions require review')
    for r in records:
        if not re.fullmatch(r'[a-f0-9]{64}', r['sha256']) or not r.get('verified'):
            raise ValueError('Unverified document')
        path = root / 'private' / (r['sha256'] + '.pdf')
        if hashlib.sha256(path.read_bytes()).hexdigest() != r['sha256']:
            raise ValueError('Original PDF integrity mismatch')

    def signature(doc_id, expires):
        return hmac.new(key.encode(), f'{doc_id}:{expires}'.encode(), hashlib.sha256).hexdigest()

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return response

    @app.get('/health')
    def health():
        return jsonify(status='ok', service='landbridge-coa', documents=len(records))

    @app.get('/lookup')
    def lookup():
        raw = request.args.get('q', '').strip()
        if len(raw) > 80 or not re.fullmatch(r'[A-Za-z0-9\s-]{3,80}', raw):
            return jsonify(error='invalid_query'), 400
        q = normalize(raw)
        if len(q) < 3:
            return jsonify(error='invalid_query'), 400
        matches = []
        expiry = int(time.time()) + 600
        for r in records:
            codes = [r['code']] + r.get('aliases', [])
            identifiers = codes + [r['lot']] + [code + r['lot'] for code in codes]
            if q not in {normalize(v) for v in identifiers}:
                continue
            doc_id = r['sha256']
            matches.append(dict(code=r['code'], lot=r['lot'], size=r['size'],
                                filename=r['filename'],
                                download=f'/api/coa/download/{doc_id}?expires={expiry}&signature={signature(doc_id, expiry)}'))
        matches.sort(key=lambda r: (r['lot'], r['code']), reverse=True)
        return jsonify(results=matches, count=len(matches))

    @app.get('/download/<doc_id>')
    def download(doc_id):
        try:
            expires = int(request.args.get('expires', '0'))
        except ValueError:
            return jsonify(error='invalid_link'), 403
        now = int(time.time())
        supplied = request.args.get('signature', '')
        if (not re.fullmatch(r'[a-f0-9]{64}', supplied) or
                expires <= now or expires > now + 600 or
                not hmac.compare_digest(supplied, signature(doc_id, expires))):
            return jsonify(error='expired_or_invalid_link'), 403
        record = documents.get(doc_id)
        if record is None:
            return jsonify(error='not_found'), 404
        try:
            content = (root / 'private' / (doc_id + '.pdf')).read_bytes()
        except OSError:
            return jsonify(error='temporarily_unavailable'), 503
        if hashlib.sha256(content).hexdigest() != doc_id:
            return jsonify(error='integrity_error'), 503
        return send_file(io.BytesIO(content), mimetype='application/pdf',
                         as_attachment=True, download_name=record['filename'])

    return app
