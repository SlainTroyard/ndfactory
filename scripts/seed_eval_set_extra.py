#!/usr/bin/env python3
"""Append additional samples to reach 50 vuln + 50 safe = 100 total."""
import json
from pathlib import Path

EVAL_PATH = Path("data/distil/samples_eval.jsonl")

EXTRA = [
    # Additional CWE-79 XSS safe
    {"id":"eval-xss-safe-003","source":"manual_owasp","cwe_id":None,"language":"python",
     "vulnerable_code":"from django.utils.html import escape\nreturn HttpResponse(f'<h1>{escape(name)}</h1>')",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},
    {"id":"eval-xss-safe-004","source":"manual_owasp","cwe_id":None,"language":"javascript",
     "vulnerable_code":"const el = document.createElement('span');\nel.textContent = userInput;\ndocument.body.appendChild(el);",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},

    # Additional path traversal safe
    {"id":"eval-path-safe-002","source":"manual_owasp","cwe_id":None,"language":"python",
     "vulnerable_code":"from pathlib import Path\nBASE = Path('/var/data').resolve()\ndef read_file(name):\n    p = (BASE / name).resolve()\n    if not str(p).startswith(str(BASE)):\n        raise ValueError('Path escape')\n    return p.read_text()",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},

    # Additional SQL safe
    {"id":"eval-sqli-safe-004","source":"manual_owasp","cwe_id":None,"language":"python",
     "vulnerable_code":"from django.db import connection\nwith connection.cursor() as cursor:\n    cursor.execute('SELECT * FROM users WHERE name = %s', [username])\n    return cursor.fetchone()",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},

    # Additional cmd injection safe
    {"id":"eval-cmd-safe-002","source":"manual_owasp","cwe_id":None,"language":"python",
     "vulnerable_code":"import subprocess, shlex\ncmd = ['git', 'log', '--oneline', '-n', str(max(1, min(count, 100)))]\nresult = subprocess.run(cmd, capture_output=True, text=True, check=True)",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},

    # Additional crypto safe
    {"id":"eval-crypto-safe-002","source":"manual_owasp","cwe_id":None,"language":"python",
     "vulnerable_code":"from cryptography.fernet import Fernet\nkey = Fernet.generate_key()\nf = Fernet(key)\nencrypted = f.encrypt(b'secret data')",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},

    # More safe misc
    {"id":"eval-safe-misc-009","source":"manual_owasp","cwe_id":None,"language":"python",
     "vulnerable_code":"import logging\nlogger = logging.getLogger(__name__)\ndef process(data):\n    logger.info('Processing %d items', len(data))\n    try:\n        return [transform(d) for d in data]\n    except ValueError as e:\n        logger.warning('Invalid data: %s', e)\n        raise",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},
    {"id":"eval-safe-misc-010","source":"manual_owasp","cwe_id":None,"language":"python",
     "vulnerable_code":"import os, stat\ndef check_perms(path):\n    mode = os.stat(path).st_mode\n    if mode & stat.S_IWOTH:\n        raise ValueError(f'World-writable: {path}')\n    return True",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},
    {"id":"eval-safe-misc-011","source":"manual_owasp","cwe_id":None,"language":"python",
     "vulnerable_code":"import re\nTAG_RE = re.compile(r'<[^>]*>')\ndef strip_tags(html):\n    return TAG_RE.sub('', html)",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},
    {"id":"eval-safe-misc-012","source":"manual_owasp","cwe_id":None,"language":"c",
     "vulnerable_code":"#include <stdlib.h>\nint *create_array(size_t n) {\n    if (n > SIZE_MAX / sizeof(int)) return NULL;\n    int *arr = calloc(n, sizeof(int));\n    if (!arr) return NULL;\n    return arr;\n}",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},

    # Additional vulnerable samples to reach 50
    # CWE-190: Integer Overflow
    {"id":"eval-int-001","source":"manual_owasp","cwe_id":"CWE-190","language":"c",
     "vulnerable_code":"void *safe_malloc(int count, int size) {\n    int total = count * size;\n    return malloc(total);\n}",
     "fixed_code":"void *safe_malloc(size_t count, size_t size) {\n    if (count > SIZE_MAX / size) return NULL;\n    return calloc(count, size);\n}",
     "is_safe":False,"ground_truth":{"has_vuln":True,"cwe_id":"CWE-190","vuln_type":"Integer Overflow","severity":"HIGH","fix_reference":"Check multiplication overflow before malloc"}},
    {"id":"eval-int-002","source":"manual_owasp","cwe_id":"CWE-190","language":"c",
     "vulnerable_code":"int parse_length(char *input) {\n    int len = atoi(input);\n    char *buf = malloc(len);\n    return buf ? 0 : -1;\n}",
     "fixed_code":"int parse_length(char *input) {\n    long len = strtol(input, NULL, 10);\n    if (len <= 0 || len > MAX_ALLOC) return -1;\n    char *buf = malloc((size_t)len);\n    return buf ? 0 : -1;\n}",
     "is_safe":False,"ground_truth":{"has_vuln":True,"cwe_id":"CWE-190","vuln_type":"Integer Overflow","severity":"HIGH","fix_reference":"Use strtol with bounds checking"}},

    # CWE-798: Hardcoded Credentials
    {"id":"eval-hard-001","source":"manual_owasp","cwe_id":"CWE-798","language":"python",
     "vulnerable_code":"API_KEY = 'sk-1234567890abcdef'\ndef call_api():\n    return requests.get('https://api.example.com', headers={'Authorization': f'Bearer {API_KEY}'})",
     "fixed_code":"import os\ndef call_api():\n    api_key = os.environ.get('API_KEY')\n    if not api_key:\n        raise RuntimeError('API_KEY not set')\n    return requests.get('https://api.example.com', headers={'Authorization': f'Bearer {api_key}'})",
     "is_safe":False,"ground_truth":{"has_vuln":True,"cwe_id":"CWE-798","vuln_type":"Hardcoded Credentials","severity":"CRITICAL","fix_reference":"Read credentials from environment variables"}},
    {"id":"eval-hard-002","source":"manual_owasp","cwe_id":"CWE-798","language":"java",
     "vulnerable_code":"private static final String DB_PASSWORD = \"admin123\";\nConnection conn = DriverManager.getConnection(url, \"admin\", DB_PASSWORD);",
     "fixed_code":"String dbPassword = System.getenv(\"DB_PASSWORD\");\nif (dbPassword == null) throw new IllegalStateException(\"DB_PASSWORD not set\");\nConnection conn = DriverManager.getConnection(url, \"admin\", dbPassword);",
     "is_safe":False,"ground_truth":{"has_vuln":True,"cwe_id":"CWE-798","vuln_type":"Hardcoded Credentials","severity":"CRITICAL","fix_reference":"Use environment variables for secrets"}},

    # CWE-601: Open Redirect
    {"id":"eval-redir-001","source":"manual_owasp","cwe_id":"CWE-601","language":"python",
     "vulnerable_code":"@app.route('/redirect')\ndef redirect_to():\n    return redirect(request.args.get('url'))",
     "fixed_code":"from urllib.parse import urlparse, urljoin\n@app.route('/redirect')\ndef redirect_to():\n    url = request.args.get('url')\n    parsed = urlparse(url)\n    if parsed.netloc and parsed.netloc != request.host:\n        abort(400, 'External redirect not allowed')\n    return redirect(url)",
     "is_safe":False,"ground_truth":{"has_vuln":True,"cwe_id":"CWE-601","vuln_type":"Open Redirect","severity":"MEDIUM","fix_reference":"Validate redirect URL is same-origin"}},
    {"id":"eval-redir-002","source":"manual_owasp","cwe_id":"CWE-601","language":"javascript",
     "vulnerable_code":"app.get('/redirect', (req, res) => {\n    res.redirect(req.query.url);\n});",
     "fixed_code":"app.get('/redirect', (req, res) => {\n    const url = new URL(req.query.url);\n    if (url.hostname !== req.hostname) {\n        return res.status(400).send('Invalid redirect');\n    }\n    res.redirect(req.query.url);\n});",
     "is_safe":False,"ground_truth":{"has_vuln":True,"cwe_id":"CWE-601","vuln_type":"Open Redirect","severity":"MEDIUM","fix_reference":"Check redirect target hostname matches request hostname"}},

    # CWE-476: NULL Pointer Dereference
    {"id":"eval-null-001","source":"manual_owasp","cwe_id":"CWE-476","language":"c",
     "vulnerable_code":"char *lookup_user(int id) {\n    char *name = db_find(\"users\", id);\n    printf(\"User: %s\\n\", name);\n    return name;\n}",
     "fixed_code":"char *lookup_user(int id) {\n    char *name = db_find(\"users\", id);\n    if (name == NULL) {\n        fprintf(stderr, \"User %d not found\\n\", id);\n        return NULL;\n    }\n    printf(\"User: %s\\n\", name);\n    return name;\n}",
     "is_safe":False,"ground_truth":{"has_vuln":True,"cwe_id":"CWE-476","vuln_type":"NULL Pointer Dereference","severity":"MEDIUM","fix_reference":"Check for NULL before dereferencing"}},
    {"id":"eval-null-002","source":"manual_owasp","cwe_id":"CWE-476","language":"cpp",
     "vulnerable_code":"std::shared_ptr<Config> load(const std::string &path) {\n    auto config = Config::from_file(path);\n    return std::move(config);\n}\nvoid init() {\n    auto c = load(\"/etc/app.conf\");\n    c->validate();\n}",
     "fixed_code":"std::shared_ptr<Config> load(const std::string &path) {\n    auto config = Config::from_file(path);\n    return config;\n}\nvoid init() {\n    auto c = load(\"/etc/app.conf\");\n    if (!c) throw std::runtime_error(\"Failed to load config\");\n    c->validate();\n}",
     "is_safe":False,"ground_truth":{"has_vuln":True,"cwe_id":"CWE-476","vuln_type":"NULL Pointer Dereference","severity":"MEDIUM","fix_reference":"Check return value before calling methods"}},

    # Additional safe misc
    {"id":"eval-safe-misc-013","source":"manual_owasp","cwe_id":None,"language":"java",
     "vulnerable_code":"@Bean\npublic SecurityFilterChain filterChain(HttpSecurity http) throws Exception {\n    return http\n        .authorizeHttpRequests(auth -> auth\n            .requestMatchers(\"/api/admin/**\").hasRole(\"ADMIN\")\n            .requestMatchers(\"/api/**\").authenticated()\n            .anyRequest().permitAll())\n        .csrf(CsrfConfigurer::disable)\n        .sessionManagement(s -> s.sessionCreationPolicy(STATELESS))\n        .build();\n}",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},
    {"id":"eval-safe-misc-014","source":"manual_owasp","cwe_id":None,"language":"python",
     "vulnerable_code":"import os, stat\nos.umask(0o077)\nwith open(os.open('/etc/config.json', os.O_CREAT | os.O_WRONLY, stat.S_IRUSR | stat.S_IWUSR), 'w') as f:\n    json.dump(config, f)",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},
    {"id":"eval-safe-misc-015","source":"manual_owasp","cwe_id":None,"language":"c",
     "vulnerable_code":"#include <string.h>\n#include <stdlib.h>\nchar *dup_string(const char *src) {\n    if (!src) return NULL;\n    size_t len = strlen(src);\n    char *dst = malloc(len + 1);\n    if (dst) memcpy(dst, src, len + 1);\n    return dst;\n}",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},
    {"id":"eval-safe-misc-016","source":"manual_owasp","cwe_id":None,"language":"python",
     "vulnerable_code":"import hmac, hashlib, time\nWEBHOOK_SECRET = os.environ['WEBHOOK_SECRET']\ndef verify_webhook(body, sig, timestamp):\n    if abs(time.time() - int(timestamp)) > 300:\n        return False\n    expected = hmac.new(WEBHOOK_SECRET.encode(), f'{timestamp}.{body}'.encode(), hashlib.sha256).hexdigest()\n    return hmac.compare_digest(expected, sig)",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},
    {"id":"eval-safe-misc-017","source":"manual_owasp","cwe_id":None,"language":"python",
     "vulnerable_code":"import unicodedata\ndef sanitize_filename(name):\n    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()\n    return ''.join(c for c in name if c.isalnum() or c in '._-')[:255]",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},
    {"id":"eval-safe-misc-018","source":"manual_owasp","cwe_id":None,"language":"python",
     "vulnerable_code":"import threading\n_local = threading.local()\ndef get_current_user():\n    return getattr(_local, 'user', None)\ndef set_current_user(user):\n    _local.user = user",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},
    {"id":"eval-safe-misc-019","source":"manual_owasp","cwe_id":None,"language":"python",
     "vulnerable_code":"from redis import Redis\nredis = Redis(decode_responses=True, socket_connect_timeout=2)\ndef rate_limit(key, max_req=60, window=60):\n    pipe = redis.pipeline()\n    now = time.time()\n    pipe.zremrangebyscore(key, 0, now - window)\n    pipe.zcard(key)\n    pipe.zadd(key, {str(now): now})\n    pipe.expire(key, window + 1)\n    _, count, _, _ = pipe.execute()\n    return count <= max_req",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},
    {"id":"eval-safe-misc-020","source":"manual_owasp","cwe_id":None,"language":"go",
     "vulnerable_code":"func copyFile(dst, src string) error {\n    s, err := os.Open(src)\n    if err != nil { return err }\n    defer s.Close()\n    d, err := os.OpenFile(dst, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o640)\n    if err != nil { return err }\n    defer d.Close()\n    _, err = io.Copy(d, s)\n    return err\n}",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},
    {"id":"eval-safe-misc-021","source":"manual_owasp","cwe_id":None,"language":"python",
     "vulnerable_code":"from typing import Final\nMAX_RETRIES: Final = 3\ndef connect():\n    for i in range(MAX_RETRIES):\n        try:\n            return _do_connect(timeout=5 * (i + 1))\n        except TimeoutError:\n            continue\n    raise ConnectionError('Max retries exceeded')",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},
    {"id":"eval-safe-misc-022","source":"manual_owasp","cwe_id":None,"language":"python",
     "vulnerable_code":"import json, jsonschema\nSCHEMA = {'type': 'object', 'properties': {'name': {'type': 'string', 'maxLength': 100}, 'age': {'type': 'integer', 'minimum': 0, 'maximum': 150}}, 'required': ['name', 'age']}\ndef validate_user(data):\n    jsonschema.validate(data, SCHEMA)\n    return True",
     "is_safe":True,"ground_truth":{"has_vuln":False,"cwe_id":None,"vuln_type":"N/A","severity":"NONE"}},
]


def main():
    existing = []
    if EVAL_PATH.exists():
        with open(EVAL_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    existing.append(json.loads(line))
    existing_ids = {s["id"] for s in existing}

    new_samples = [s for s in EXTRA if s["id"] not in existing_ids]
    all_samples = existing + new_samples

    vuln_count = sum(1 for s in all_samples if not s["is_safe"])
    safe_count = sum(1 for s in all_samples if s["is_safe"])

    print(f"Before: {len(existing)} samples ({sum(1 for s in existing if not s['is_safe'])} vuln + {sum(1 for s in existing if s['is_safe'])} safe)")
    print(f"Added:  {len(new_samples)} samples")
    print(f"After:  {len(all_samples)} samples ({vuln_count} vuln + {safe_count} safe)")

    with open(EVAL_PATH, "w", encoding="utf-8") as f:
        for s in all_samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    print(f"Saved to {EVAL_PATH}")


if __name__ == "__main__":
    main()
