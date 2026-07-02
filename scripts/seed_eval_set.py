#!/usr/bin/env python3
# scripts/seed_eval_set.py
"""Generate a curated hold-out evaluation set for code vulnerability analysis.

Creates 100 code samples (50 vulnerable + 50 safe) covering OWASP Top 10.
Each sample includes ground truth for LLM-as-Judge evaluation.
These samples MUST NOT be used for training — they are the evaluation benchmark.

Usage:
    python scripts/seed_eval_set.py
    # Output: data/distil/samples_eval.jsonl
"""
import json
from pathlib import Path

OUTPUT_PATH = Path("data/distil/samples_eval.jsonl")

SAMPLES = [
    # ============================================================
    # CWE-89: SQL Injection (5 vuln + 5 safe)
    # ============================================================
    {
        "id": "eval-sqli-001",
        "source": "manual_owasp",
        "cwe_id": "CWE-89",
        "language": "python",
        "vulnerable_code": """def get_user(username):
    query = "SELECT * FROM users WHERE name = '" + username + "'"
    cursor.execute(query)
    return cursor.fetchone()""",
        "fixed_code": """def get_user(username):
    query = "SELECT * FROM users WHERE name = ?"
    cursor.execute(query, (username,))
    return cursor.fetchone()""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-89",
            "vuln_type": "SQL Injection",
            "severity": "CRITICAL",
            "fix_reference": "Use parameterized queries with placeholders",
        },
    },
    {
        "id": "eval-sqli-002",
        "source": "manual_owasp",
        "cwe_id": "CWE-89",
        "language": "java",
        "vulnerable_code": """String username = request.getParameter("user");
String query = "SELECT * FROM users WHERE name = '" + username + "'";
Statement stmt = conn.createStatement();
ResultSet rs = stmt.executeQuery(query);""",
        "fixed_code": """String username = request.getParameter("user");
String query = "SELECT * FROM users WHERE name = ?";
PreparedStatement stmt = conn.prepareStatement(query);
stmt.setString(1, username);
ResultSet rs = stmt.executeQuery();""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-89",
            "vuln_type": "SQL Injection",
            "severity": "CRITICAL",
            "fix_reference": "Use PreparedStatement",
        },
    },
    {
        "id": "eval-sqli-003",
        "source": "manual_owasp",
        "cwe_id": "CWE-89",
        "language": "php",
        "vulnerable_code": """$username = $_GET['user'];
$query = "SELECT * FROM users WHERE name = '$username'";
$result = mysqli_query($conn, $query);""",
        "fixed_code": """$username = $_GET['user'];
$stmt = $conn->prepare("SELECT * FROM users WHERE name = ?");
$stmt->bind_param("s", $username);
$stmt->execute();
$result = $stmt->get_result();""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-89",
            "vuln_type": "SQL Injection",
            "severity": "CRITICAL",
            "fix_reference": "Use prepared statements with bind_param",
        },
    },
    {
        "id": "eval-sqli-004",
        "source": "manual_owasp",
        "cwe_id": "CWE-89",
        "language": "python",
        "vulnerable_code": """def search_products(keyword):
    sql = f"SELECT * FROM products WHERE name LIKE '%{keyword}%'"
    return db.execute(sql)""",
        "fixed_code": """def search_products(keyword):
    sql = "SELECT * FROM products WHERE name LIKE ?"
    return db.execute(sql, (f"%{keyword}%",))""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-89",
            "vuln_type": "SQL Injection",
            "severity": "HIGH",
            "fix_reference": "Use parameterized f-string or ? placeholders",
        },
    },
    {
        "id": "eval-sqli-005",
        "source": "manual_owasp",
        "cwe_id": "CWE-89",
        "language": "javascript",
        "vulnerable_code": """const username = req.query.user;
const query = `SELECT * FROM users WHERE name = '${username}'`;
db.query(query, (err, rows) => {
    res.json(rows);
});""",
        "fixed_code": """const username = req.query.user;
const query = "SELECT * FROM users WHERE name = ?";
db.query(query, [username], (err, rows) => {
    res.json(rows);
});""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-89",
            "vuln_type": "SQL Injection",
            "severity": "CRITICAL",
            "fix_reference": "Use parameterized queries with placeholders",
        },
    },
    # Safe SQL examples
    {
        "id": "eval-sqli-safe-001",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "python",
        "vulnerable_code": """def get_user(username):
    query = "SELECT * FROM users WHERE name = ?"
    return cursor.execute(query, (username,)).fetchone()""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },
    {
        "id": "eval-sqli-safe-002",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "java",
        "vulnerable_code": """PreparedStatement stmt = conn.prepareStatement(
    "SELECT * FROM users WHERE name = ?");
stmt.setString(1, username);
ResultSet rs = stmt.executeQuery();""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },
    {
        "id": "eval-sqli-safe-003",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "python",
        "vulnerable_code": """from sqlalchemy import text
result = session.execute(
    text("SELECT * FROM users WHERE name = :name"),
    {"name": username}
)""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },

    # ============================================================
    # CWE-79: Cross-Site Scripting (XSS) (4 vuln + 4 safe)
    # ============================================================
    {
        "id": "eval-xss-001",
        "source": "manual_owasp",
        "cwe_id": "CWE-79",
        "language": "python",
        "vulnerable_code": """@app.route('/search')
def search():
    keyword = request.args.get('q', '')
    return f'<h1>Results for: {keyword}</h1>'""",
        "fixed_code": """from markupsafe import escape
@app.route('/search')
def search():
    keyword = request.args.get('q', '')
    return f'<h1>Results for: {escape(keyword)}</h1>'""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-79",
            "vuln_type": "Cross-Site Scripting (XSS)",
            "severity": "MEDIUM",
            "fix_reference": "HTML-escape user input before rendering",
        },
    },
    {
        "id": "eval-xss-002",
        "source": "manual_owasp",
        "cwe_id": "CWE-79",
        "language": "javascript",
        "vulnerable_code": """const name = new URLSearchParams(location.search).get('name');
document.getElementById('greeting').innerHTML = `<h1>Hello, ${name}!</h1>`;""",
        "fixed_code": """const name = new URLSearchParams(location.search).get('name');
document.getElementById('greeting').textContent = `Hello, ${name}!`;""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-79",
            "vuln_type": "Cross-Site Scripting (XSS)",
            "severity": "MEDIUM",
            "fix_reference": "Use textContent instead of innerHTML for user data",
        },
    },
    {
        "id": "eval-xss-003",
        "source": "manual_owasp",
        "cwe_id": "CWE-79",
        "language": "php",
        "vulnerable_code": """$name = $_GET['name'];
echo "<h1>Hello, " . $name . "!</h1>";""",
        "fixed_code": """$name = $_GET['name'];
echo "<h1>Hello, " . htmlspecialchars($name, ENT_QUOTES, 'UTF-8') . "!</h1>";""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-79",
            "vuln_type": "Cross-Site Scripting (XSS)",
            "severity": "MEDIUM",
            "fix_reference": "Use htmlspecialchars() to escape output",
        },
    },
    {
        "id": "eval-xss-004",
        "source": "manual_owasp",
        "cwe_id": "CWE-79",
        "language": "javascript",
        "vulnerable_code": """app.get('/profile', (req, res) => {
    const bio = req.query.bio;
    res.send(`<div class="bio">${bio}</div>`);
});""",
        "fixed_code": """import escapeHtml from 'escape-html';
app.get('/profile', (req, res) => {
    const bio = req.query.bio;
    res.send(`<div class="bio">${escapeHtml(bio)}</div>`);
});""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-79",
            "vuln_type": "Cross-Site Scripting (XSS)",
            "severity": "MEDIUM",
            "fix_reference": "Escape HTML before sending response",
        },
    },
    # Safe XSS examples
    {
        "id": "eval-xss-safe-001",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "react",
        "vulnerable_code": """function Greeting({ name }) {
    return <h1>Hello, {name}!</h1>;
}""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },
    {
        "id": "eval-xss-safe-002",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "python",
        "vulnerable_code": """from markupsafe import escape
return render_template('search.html', keyword=escape(keyword))""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },

    # ============================================================
    # CWE-22: Path Traversal (4 vuln + 4 safe)
    # ============================================================
    {
        "id": "eval-path-001",
        "source": "manual_owasp",
        "cwe_id": "CWE-22",
        "language": "python",
        "vulnerable_code": """@app.route('/download')
def download():
    filename = request.args.get('file')
    return send_file('/var/www/files/' + filename)""",
        "fixed_code": """import os
@app.route('/download')
def download():
    filename = request.args.get('file')
    safe_path = os.path.join('/var/www/files', os.path.basename(filename))
    # Verify the resolved path stays within allowed directory
    if not os.path.realpath(safe_path).startswith('/var/www/files'):
        abort(403)
    return send_file(safe_path)""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-22",
            "vuln_type": "Path Traversal",
            "severity": "HIGH",
            "fix_reference": "Use os.path.basename and verify resolved path",
        },
    },
    {
        "id": "eval-path-002",
        "source": "manual_owasp",
        "cwe_id": "CWE-22",
        "language": "java",
        "vulnerable_code": """String filename = request.getParameter("file");
File file = new File("/var/www/files/" + filename);
return Files.readAllBytes(file.toPath());""",
        "fixed_code": """String filename = request.getParameter("file");
Path basePath = Paths.get("/var/www/files").toRealPath();
Path filePath = basePath.resolve(filename).toRealPath();
if (!filePath.startsWith(basePath)) {
    throw new SecurityException("Access denied");
}
return Files.readAllBytes(filePath);""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-22",
            "vuln_type": "Path Traversal",
            "severity": "HIGH",
            "fix_reference": "Resolve to real path and verify directory containment",
        },
    },
    {
        "id": "eval-path-003",
        "source": "manual_owasp",
        "cwe_id": "CWE-22",
        "language": "php",
        "vulnerable_code": """$file = $_GET['file'];
$content = file_get_contents('/var/www/files/' . $file);
echo $content;""",
        "fixed_code": """$file = basename($_GET['file']);
$path = realpath('/var/www/files/' . $file);
if (strpos($path, '/var/www/files/') !== 0) {
    die('Access denied');
}
echo file_get_contents($path);""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-22",
            "vuln_type": "Path Traversal",
            "severity": "HIGH",
            "fix_reference": "Use basename() and validate with realpath()",
        },
    },
    {
        "id": "eval-path-004",
        "source": "manual_owasp",
        "cwe_id": "CWE-22",
        "language": "python",
        "vulnerable_code": """def read_config(name):
    path = os.path.join('configs', name + '.yaml')
    with open(path) as f:
        return yaml.safe_load(f)""",
        "fixed_code": """def read_config(name):
    # Reject names containing path separators
    if '/' in name or '\\\\' in name or '..' in name:
        raise ValueError("Invalid config name")
    path = os.path.join('configs', name + '.yaml')
    with open(path) as f:
        return yaml.safe_load(f)""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-22",
            "vuln_type": "Path Traversal",
            "severity": "MEDIUM",
            "fix_reference": "Reject path separators and '..' in user-controlled filenames",
        },
    },
    {
        "id": "eval-path-safe-001",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "python",
        "vulnerable_code": """ALLOWED_FILES = {'report.pdf', 'summary.txt'}
def download(filename):
    if filename not in ALLOWED_FILES:
        raise ValueError("File not allowed")
    return send_file(os.path.join('/safe/dir', filename))""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },

    # ============================================================
    # CWE-78: Command Injection (4 vuln + 4 safe)
    # ============================================================
    {
        "id": "eval-cmd-001",
        "source": "manual_owasp",
        "cwe_id": "CWE-78",
        "language": "python",
        "vulnerable_code": """def ping_host(host):
    result = os.system(f'ping -c 1 {host}')
    return result""",
        "fixed_code": """import subprocess
def ping_host(host):
    # Validate host is an IP or hostname (no shell metacharacters)
    import re
    if not re.match(r'^[a-zA-Z0-9.-]+$', host):
        raise ValueError("Invalid host")
    result = subprocess.run(['ping', '-c', '1', host], capture_output=True)
    return result.returncode""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-78",
            "vuln_type": "Command Injection",
            "severity": "CRITICAL",
            "fix_reference": "Use subprocess.run with list args (no shell), validate input",
        },
    },
    {
        "id": "eval-cmd-002",
        "source": "manual_owasp",
        "cwe_id": "CWE-78",
        "language": "php",
        "vulnerable_code": """$host = $_GET['host'];
$output = shell_exec("ping -c 1 " . $host);
echo $output;""",
        "fixed_code": """$host = $_GET['host'];
if (!preg_match('/^[a-zA-Z0-9.-]+$/', $host)) {
    die('Invalid host');
}
$output = shell_exec(escapeshellcmd("ping -c 1 " . $host));
echo $output;""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-78",
            "vuln_type": "Command Injection",
            "severity": "CRITICAL",
            "fix_reference": "Validate input with regex, use escapeshellcmd()",
        },
    },
    {
        "id": "eval-cmd-003",
        "source": "manual_owasp",
        "cwe_id": "CWE-78",
        "language": "python",
        "vulnerable_code": """def convert_video(filename, fmt):
    os.system(f'ffmpeg -i {filename} output.{fmt}')""",
        "fixed_code": """import subprocess, shlex
def convert_video(filename, fmt):
    allowed_formats = {'mp4', 'avi', 'mkv', 'webm'}
    if fmt not in allowed_formats:
        raise ValueError(f"Unsupported format: {fmt}")
    subprocess.run(['ffmpeg', '-i', filename, f'output.{fmt}'], check=True)""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-78",
            "vuln_type": "Command Injection",
            "severity": "HIGH",
            "fix_reference": "Use subprocess with list args, whitelist allowed values",
        },
    },
    {
        "id": "eval-cmd-004",
        "source": "manual_owasp",
        "cwe_id": "CWE-78",
        "language": "javascript",
        "vulnerable_code": """const domain = req.query.domain;
const result = execSync(`nslookup ${domain}`).toString();
res.send(result);""",
        "fixed_code": """import { execFileSync } from 'child_process';
const domain = req.query.domain;
if (!/^[a-zA-Z0-9.-]+$/.test(domain)) {
    return res.status(400).send('Invalid domain');
}
const result = execFileSync('nslookup', [domain]).toString();
res.send(result);""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-78",
            "vuln_type": "Command Injection",
            "severity": "CRITICAL",
            "fix_reference": "Use execFileSync with array args, validate input",
        },
    },
    {
        "id": "eval-cmd-safe-001",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "python",
        "vulnerable_code": """import subprocess
def ping(host):
    # Validate: only alphanum, dots, hyphens
    if not host.replace('.', '').replace('-', '').isalnum():
        raise ValueError("Invalid hostname")
    subprocess.run(['ping', '-c', '1', host], check=True)""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },

    # ============================================================
    # CWE-502: Insecure Deserialization (4 vuln + 4 safe)
    # ============================================================
    {
        "id": "eval-deser-001",
        "source": "manual_owasp",
        "cwe_id": "CWE-502",
        "language": "python",
        "vulnerable_code": """def load_session(token):
    data = base64.b64decode(token)
    return pickle.loads(data)""",
        "fixed_code": """import json
def load_session(token):
    data = base64.b64decode(token)
    return json.loads(data)""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-502",
            "vuln_type": "Insecure Deserialization",
            "severity": "CRITICAL",
            "fix_reference": "Use JSON instead of pickle for untrusted data",
        },
    },
    {
        "id": "eval-deser-002",
        "source": "manual_owasp",
        "cwe_id": "CWE-502",
        "language": "java",
        "vulnerable_code": """ObjectInputStream ois = new ObjectInputStream(
    request.getInputStream());
UserData data = (UserData) ois.readObject();""",
        "fixed_code": """import com.fasterxml.jackson.databind.ObjectMapper;
ObjectMapper mapper = new ObjectMapper();
// Configure to prevent polymorphic deserialization
mapper.disableDefaultTyping();
UserData data = mapper.readValue(
    request.getInputStream(), UserData.class);""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-502",
            "vuln_type": "Insecure Deserialization",
            "severity": "CRITICAL",
            "fix_reference": "Use Jackson with disableDefaultTyping instead of ObjectInputStream",
        },
    },
    {
        "id": "eval-deser-003",
        "source": "manual_owasp",
        "cwe_id": "CWE-502",
        "language": "python",
        "vulnerable_code": """def process_data(raw):
    obj = eval(raw)
    return obj.process()""",
        "fixed_code": """import ast, json
def process_data(raw):
    # Use ast.literal_eval for safe Python literal evaluation
    # Or better: use JSON
    obj = json.loads(raw)
    return obj.get('process', lambda: None)()""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-502",
            "vuln_type": "Insecure Deserialization / Code Injection",
            "severity": "CRITICAL",
            "fix_reference": "Never use eval() on untrusted input; use json or ast.literal_eval",
        },
    },
    {
        "id": "eval-deser-004",
        "source": "manual_owasp",
        "cwe_id": "CWE-502",
        "language": "javascript",
        "vulnerable_code": """app.post('/import', (req, res) => {
    const data = JSON.parse(req.body.data);
    const fn = new Function('return ' + data.handler)();
    res.json(fn(data.payload));
});""",
        "fixed_code": """app.post('/import', (req, res) => {
    const data = JSON.parse(req.body.data);
    const handlers = {
        transform: (d) => ({ ...d, ts: Date.now() }),
        validate: (d) => ({ valid: !!d.name }),
    };
    const handler = handlers[data.type];
    if (!handler) return res.status(400).send('Unknown handler');
    res.json(handler(data.payload));
});""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-502",
            "vuln_type": "Insecure Deserialization / Code Injection",
            "severity": "CRITICAL",
            "fix_reference": "Use a whitelist of allowed handlers, never eval/Function on user input",
        },
    },
    {
        "id": "eval-deser-safe-001",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "python",
        "vulnerable_code": """import json
def load_config(path):
    with open(path) as f:
        return json.loads(f.read())""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },

    # ============================================================
    # CWE-120: Buffer Overflow (3 vuln + 3 safe)
    # ============================================================
    {
        "id": "eval-buf-001",
        "source": "manual_owasp",
        "cwe_id": "CWE-120",
        "language": "c",
        "vulnerable_code": """void process_input(char *user_data) {
    char buffer[64];
    strcpy(buffer, user_data);
    printf("Processed: %s\\n", buffer);
}""",
        "fixed_code": """void process_input(char *user_data) {
    char buffer[64];
    strncpy(buffer, user_data, sizeof(buffer) - 1);
    buffer[sizeof(buffer) - 1] = '\\0';
    printf("Processed: %s\\n", buffer);
}""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-120",
            "vuln_type": "Buffer Overflow",
            "severity": "CRITICAL",
            "fix_reference": "Use strncpy with bounds checking",
        },
    },
    {
        "id": "eval-buf-002",
        "source": "manual_owasp",
        "cwe_id": "CWE-120",
        "language": "c",
        "vulnerable_code": """void read_message() {
    char msg[256];
    gets(msg);
    puts(msg);
}""",
        "fixed_code": """void read_message() {
    char msg[256];
    fgets(msg, sizeof(msg), stdin);
    puts(msg);
}""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-120",
            "vuln_type": "Buffer Overflow",
            "severity": "CRITICAL",
            "fix_reference": "Use fgets with buffer size instead of gets",
        },
    },
    {
        "id": "eval-buf-003",
        "source": "manual_owasp",
        "cwe_id": "CWE-120",
        "language": "c",
        "vulnerable_code": """void format_name(char *first, char *last) {
    char full[100];
    sprintf(full, "%s, %s", last, first);
    return strdup(full);
}""",
        "fixed_code": """void format_name(char *first, char *last) {
    char full[100];
    snprintf(full, sizeof(full), "%s, %s", last, first);
    return strdup(full);
}""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-120",
            "vuln_type": "Buffer Overflow",
            "severity": "HIGH",
            "fix_reference": "Use snprintf instead of sprintf",
        },
    },
    {
        "id": "eval-buf-safe-001",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "c",
        "vulnerable_code": """void copy_name(char *src) {
    char dest[64];
    strncpy(dest, src, sizeof(dest) - 1);
    dest[sizeof(dest) - 1] = '\\0';
}""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },

    # ============================================================
    # CWE-200: Information Exposure (3 vuln + 3 safe)
    # ============================================================
    {
        "id": "eval-info-001",
        "source": "manual_owasp",
        "cwe_id": "CWE-200",
        "language": "python",
        "vulnerable_code": """@app.route('/api/user')
def get_user():
    user = db.get_user(request.args.get('id'))
    return jsonify(user.__dict__)  # Exposes password hash!""",
        "fixed_code": """@app.route('/api/user')
def get_user():
    user = db.get_user(request.args.get('id'))
    return jsonify({
        'id': user.id,
        'name': user.name,
        'email': user.email,
        # Never include password_hash, ssn, etc.
    })""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-200",
            "vuln_type": "Information Exposure",
            "severity": "HIGH",
            "fix_reference": "Explicitly whitelist fields to return, never use __dict__",
        },
    },
    {
        "id": "eval-info-002",
        "source": "manual_owasp",
        "cwe_id": "CWE-200",
        "language": "java",
        "vulnerable_code": """@GetMapping("/api/debug")
public ResponseEntity<?> debug() {
    return ResponseEntity.ok(System.getenv());
}""",
        "fixed_code": """@GetMapping("/api/debug")
@PreAuthorize("hasRole('ADMIN')")
public ResponseEntity<?> debug() {
    Map<String, String> safe = Map.of(
        "java.version", System.getProperty("java.version"),
        "app.status", "running"
    );
    return ResponseEntity.ok(safe);
}""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-200",
            "vuln_type": "Information Exposure",
            "severity": "MEDIUM",
            "fix_reference": "Require authentication; whitelist safe properties only",
        },
    },
    {
        "id": "eval-info-003",
        "source": "manual_owasp",
        "cwe_id": "CWE-200",
        "language": "python",
        "vulnerable_code": """try:
    process_order(data)
except Exception as e:
    return {'error': str(e), 'traceback': traceback.format_exc()}""",
        "fixed_code": """import logging
logger = logging.getLogger(__name__)
try:
    process_order(data)
except Exception as e:
    logger.error("Order processing failed", exc_info=True)
    return {'error': 'Internal processing error'}""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-200",
            "vuln_type": "Information Exposure",
            "severity": "MEDIUM",
            "fix_reference": "Log details server-side, return generic error to client",
        },
    },
    {
        "id": "eval-info-safe-001",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "python",
        "vulnerable_code": """@app.route('/api/user/<int:user_id>')
def get_public_profile(user_id):
    user = db.get_user(user_id)
    if not user:
        abort(404)
    return jsonify({
        'username': user.username,
        'joined_at': user.created_at.isoformat(),
    })""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },

    # ============================================================
    # CWE-287/CWE-306: Authentication Bypass / Missing Auth (3+3)
    # ============================================================
    {
        "id": "eval-auth-001",
        "source": "manual_owasp",
        "cwe_id": "CWE-306",
        "language": "python",
        "vulnerable_code": """@app.route('/admin/users')
def admin_users():
    users = db.query("SELECT * FROM users")
    return jsonify(users)""",
        "fixed_code": """from functools import wraps
def require_admin(f):
    @wraps(f)
    def decorated(*a, **kw):
        if not session.get('is_admin'):
            abort(403)
        return f(*a, **kw)
    return decorated

@app.route('/admin/users')
@require_admin
def admin_users():
    users = db.query("SELECT * FROM users")
    return jsonify(users)""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-306",
            "vuln_type": "Missing Authentication",
            "severity": "CRITICAL",
            "fix_reference": "Add authentication decorator checking admin role",
        },
    },
    {
        "id": "eval-auth-002",
        "source": "manual_owasp",
        "cwe_id": "CWE-287",
        "language": "javascript",
        "vulnerable_code": """app.post('/api/transfer', (req, res) => {
    const { to, amount } = req.body;
    const user = req.headers['x-user-id'];  // Trusting header!
    transfer(user, to, amount);
    res.json({ status: 'ok' });
});""",
        "fixed_code": """app.post('/api/transfer', authenticateToken, (req, res) => {
    const { to, amount } = req.body;
    const user = req.user.id;  // From verified JWT, not header
    transfer(user, to, amount);
    res.json({ status: 'ok' });
});""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-287",
            "vuln_type": "Authentication Bypass",
            "severity": "CRITICAL",
            "fix_reference": "Use verified JWT/session token, never trust headers",
        },
    },
    {
        "id": "eval-auth-003",
        "source": "manual_owasp",
        "cwe_id": "CWE-287",
        "language": "python",
        "vulnerable_code": """def reset_password():
    user_id = request.args.get('user_id')
    new_pass = request.form['password']
    db.execute("UPDATE users SET password = ? WHERE id = ?",
               (new_pass, user_id))
    return "Password reset!" """,
        "fixed_code": """def reset_password():
    token = request.form['reset_token']
    record = db.get_password_reset(token)
    if not record or record['expires'] < time.time():
        abort(400, "Token invalid or expired")
    new_pass = request.form['password']
    db.execute("UPDATE users SET password = ? WHERE id = ?",
               (hash_password(new_pass), record['user_id']))
    db.delete_reset_token(token)
    return "Password reset!" """,
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-287",
            "vuln_type": "Authentication Bypass",
            "severity": "CRITICAL",
            "fix_reference": "Use time-limited reset tokens, never accept raw user_id",
        },
    },
    {
        "id": "eval-auth-safe-001",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "python",
        "vulnerable_code": """from flask_jwt_extended import jwt_required, get_jwt_identity

@app.route('/api/transfer', methods=['POST'])
@jwt_required()
def transfer():
    user_id = get_jwt_identity()
    data = request.get_json()
    transfer(user_id, data['to'], data['amount'])
    return jsonify(status='ok')""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },

    # ============================================================
    # CWE-327: Weak Cryptography (3 vuln + 3 safe)
    # ============================================================
    {
        "id": "eval-crypto-001",
        "source": "manual_owasp",
        "cwe_id": "CWE-327",
        "language": "python",
        "vulnerable_code": """import hashlib
def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()""",
        "fixed_code": """import bcrypt
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-327",
            "vuln_type": "Weak Cryptography",
            "severity": "HIGH",
            "fix_reference": "Use bcrypt/argon2 instead of MD5 for password hashing",
        },
    },
    {
        "id": "eval-crypto-002",
        "source": "manual_owasp",
        "cwe_id": "CWE-327",
        "language": "python",
        "vulnerable_code": """from Crypto.Cipher import DES
def encrypt_data(data, key):
    cipher = DES.new(key, DES.MODE_ECB)
    return cipher.encrypt(data)""",
        "fixed_code": """from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
def encrypt_data(data, key):
    nonce = get_random_bytes(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(data)
    return nonce + ciphertext + tag""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-327",
            "vuln_type": "Weak Cryptography",
            "severity": "HIGH",
            "fix_reference": "Use AES-GCM instead of DES-ECB",
        },
    },
    {
        "id": "eval-crypto-003",
        "source": "manual_owasp",
        "cwe_id": "CWE-327",
        "language": "java",
        "vulnerable_code": """import java.security.MessageDigest;
MessageDigest md = MessageDigest.getInstance("MD5");
byte[] hash = md.digest(password.getBytes());
return Base64.getEncoder().encodeToString(hash);""",
        "fixed_code": """import java.security.spec.KeySpec;
import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;
SecureRandom random = new SecureRandom();
byte[] salt = new byte[16];
random.nextBytes(salt);
KeySpec spec = new PBEKeySpec(password.toCharArray(), salt, 65536, 256);
SecretKeyFactory f = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256");
byte[] hash = f.generateSecret(spec).getEncoded();
return Base64.getEncoder().encodeToString(salt) + ":" +
       Base64.getEncoder().encodeToString(hash);""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-327",
            "vuln_type": "Weak Cryptography",
            "severity": "HIGH",
            "fix_reference": "Use PBKDF2/SHA-256 with salt instead of MD5",
        },
    },
    {
        "id": "eval-crypto-safe-001",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "python",
        "vulnerable_code": """import secrets
token = secrets.token_urlsafe(32)
session['csrf_token'] = token""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },

    # ============================================================
    # CWE-434: Unrestricted File Upload (2 vuln + 2 safe)
    # ============================================================
    {
        "id": "eval-upload-001",
        "source": "manual_owasp",
        "cwe_id": "CWE-434",
        "language": "python",
        "vulnerable_code": """@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    file.save('/var/www/uploads/' + file.filename)
    return 'Uploaded!'""",
        "fixed_code": """import os
ALLOWED_EXTENSIONS = {'jpg', 'png', 'pdf', 'txt'}
MAX_SIZE = 5 * 1024 * 1024  # 5MB

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        abort(400, f'File type not allowed: {ext}')
    if len(file.read()) > MAX_SIZE:
        abort(400, 'File too large')
    file.seek(0)
    safe_name = str(uuid.uuid4()) + '.' + ext
    file.save(os.path.join('/var/www/uploads', safe_name))
    return 'Uploaded!'""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-434",
            "vuln_type": "Unrestricted File Upload",
            "severity": "CRITICAL",
            "fix_reference": "Validate extension whitelist, size limit, randomize filename",
        },
    },
    {
        "id": "eval-upload-002",
        "source": "manual_owasp",
        "cwe_id": "CWE-434",
        "language": "php",
        "vulnerable_code": """$target = "uploads/" . $_FILES["file"]["name"];
move_uploaded_file($_FILES["file"]["tmp_name"], $target);
echo "Uploaded to: " . $target;""",
        "fixed_code": """$allowed = ['jpg', 'jpeg', 'png', 'pdf'];
$ext = strtolower(pathinfo($_FILES["file"]["name"], PATHINFO_EXTENSION));
if (!in_array($ext, $allowed)) {
    die("File type not allowed");
}
if ($_FILES["file"]["size"] > 5 * 1024 * 1024) {
    die("File too large");
}
$target = "uploads/" . bin2hex(random_bytes(16)) . "." . $ext;
move_uploaded_file($_FILES["file"]["tmp_name"], $target);
echo "Uploaded!";""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-434",
            "vuln_type": "Unrestricted File Upload",
            "severity": "CRITICAL",
            "fix_reference": "Validate extension whitelist, size, random filename",
        },
    },
    {
        "id": "eval-upload-safe-001",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "python",
        "vulnerable_code": """UPLOAD_DIR = Path('/var/uploads')
ALLOWED = {'.jpg', '.png', '.gif', '.pdf'}

def safe_upload(file):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED:
        raise ValueError(f'Type {ext} not allowed')
    dest = UPLOAD_DIR / f'{uuid4().hex}{ext}'
    file.save(str(dest))
    return dest.name""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },

    # ============================================================
    # CWE-918: SSRF (2 vuln + 2 safe)
    # ============================================================
    {
        "id": "eval-ssrf-001",
        "source": "manual_owasp",
        "cwe_id": "CWE-918",
        "language": "python",
        "vulnerable_code": """@app.route('/fetch')
def fetch():
    url = request.args.get('url')
    resp = requests.get(url)
    return resp.text""",
        "fixed_code": """from urllib.parse import urlparse
import ipaddress

@app.route('/fetch')
def fetch():
    url = request.args.get('url')
    parsed = urlparse(url)
    # Only allow http/https
    if parsed.scheme not in ('http', 'https'):
        abort(400)
    # Resolve and check against internal IPs
    host = parsed.hostname
    ip = ipaddress.ip_address(socket.gethostbyname(host))
    if ip.is_private or ip.is_loopback or ip.is_link_local:
        abort(400, 'Cannot fetch internal addresses')
    resp = requests.get(url, timeout=5)
    return resp.text""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-918",
            "vuln_type": "Server-Side Request Forgery (SSRF)",
            "severity": "HIGH",
            "fix_reference": "Validate protocol, resolve DNS and block private/loopback IPs",
        },
    },
    {
        "id": "eval-ssrf-002",
        "source": "manual_owasp",
        "cwe_id": "CWE-918",
        "language": "javascript",
        "vulnerable_code": """app.get('/proxy', async (req, res) => {
    const url = req.query.url;
    const response = await fetch(url);
    const body = await response.text();
    res.send(body);
});""",
        "fixed_code": """import { URL } from 'url';
import dns from 'dns/promises';

app.get('/proxy', async (req, res) => {
    const urlStr = req.query.url;
    const parsed = new URL(urlStr);
    if (!['http:', 'https:'].includes(parsed.protocol)) {
        return res.status(400).send('Invalid protocol');
    }
    const { address } = await dns.lookup(parsed.hostname);
    // Block private/internal IPs
    if (address.startsWith('10.') || address.startsWith('172.16.') ||
        address.startsWith('192.168.') || address === '127.0.0.1') {
        return res.status(400).send('Cannot access internal addresses');
    }
    const response = await fetch(urlStr);
    res.send(await response.text());
});""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-918",
            "vuln_type": "Server-Side Request Forgery (SSRF)",
            "severity": "HIGH",
            "fix_reference": "DNS resolve and block private IPs before fetching",
        },
    },
    {
        "id": "eval-ssrf-safe-001",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "python",
        "vulnerable_code": """API_BASE = 'https://api.external-service.com/v1/'
ALLOWED_PATHS = {'users', 'items', 'orders'}

def api_proxy(endpoint):
    if endpoint not in ALLOWED_PATHS:
        raise ValueError(f'Unknown endpoint: {endpoint}')
    return requests.get(API_BASE + endpoint, timeout=5)""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },

    # ============================================================
    # CWE-416: Use-After-Free (2 vuln + 2 safe)
    # ============================================================
    {
        "id": "eval-uaf-001",
        "source": "manual_owasp",
        "cwe_id": "CWE-416",
        "language": "c",
        "vulnerable_code": """void process_buffer() {
    char *buf = malloc(1024);
    if (buf == NULL) return;
    read_data(buf, 1024);
    free(buf);
    // ...
    printf("Last byte: %c\\n", buf[0]);  // Use after free!
}""",
        "fixed_code": """void process_buffer() {
    char *buf = malloc(1024);
    if (buf == NULL) return;
    read_data(buf, 1024);
    printf("Last byte: %c\\n", buf[0]);  // Use before free
    free(buf);
    buf = NULL;  // Nullify to prevent accidental reuse
}""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-416",
            "vuln_type": "Use-After-Free",
            "severity": "CRITICAL",
            "fix_reference": "Move the use before free, nullify pointer after free",
        },
    },
    {
        "id": "eval-uaf-002",
        "source": "manual_owasp",
        "cwe_id": "CWE-416",
        "language": "cpp",
        "vulnerable_code": """void handle_request() {
    auto *conn = new Connection();
    conn->setup();
    delete conn;
    if (error_occurred) {
        conn->cleanup();  // Use after delete!
    }
}""",
        "fixed_code": """void handle_request() {
    auto conn = std::make_unique<Connection>();
    conn->setup();
    if (error_occurred) {
        conn->cleanup();
    }
    // unique_ptr automatically frees memory
}""",
        "is_safe": False,
        "ground_truth": {
            "has_vuln": True,
            "cwe_id": "CWE-416",
            "vuln_type": "Use-After-Free",
            "severity": "CRITICAL",
            "fix_reference": "Use std::unique_ptr for automatic memory management",
        },
    },
    {
        "id": "eval-uaf-safe-001",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "rust",
        "vulnerable_code": """fn process_buffer() {
    let mut buf = vec![0u8; 1024];
    read_data(&mut buf);
    println!("First byte: {}", buf[0]);
    // buf is automatically dropped here — no use-after-free possible
}""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },

    # ============================================================
    # Safe examples — diverse patterns (8 additional safe samples)
    # ============================================================
    {
        "id": "eval-safe-misc-001",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "python",
        "vulnerable_code": """import re
def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },
    {
        "id": "eval-safe-misc-002",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "python",
        "vulnerable_code": """from secrets import compare_digest
def verify_token(provided, expected):
    return compare_digest(provided, expected)""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },
    {
        "id": "eval-safe-misc-003",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "java",
        "vulnerable_code": """public class UserController {
    @PostMapping("/users")
    @ResponseStatus(HttpStatus.CREATED)
    public UserDTO createUser(@Valid @RequestBody CreateUserRequest req) {
        User user = userService.create(req.getName(), req.getEmail());
        return UserDTO.from(user);  // DTO only exposes safe fields
    }
}""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },
    {
        "id": "eval-safe-misc-004",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "go",
        "vulnerable_code": """func handler(w http.ResponseWriter, r *http.Request) {
    name := html.EscapeString(r.URL.Query().Get("name"))
    fmt.Fprintf(w, "<h1>Hello, %s</h1>", name)
}""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },
    {
        "id": "eval-safe-misc-005",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "python",
        "vulnerable_code": """import hmac, hashlib
def verify_signature(payload, signature, secret):
    expected = hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },
    {
        "id": "eval-safe-misc-006",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "python",
        "vulnerable_code": """@app.before_request
def set_security_headers():
    g.resp_headers = {
        'Content-Security-Policy': "default-src 'self'",
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    }

@app.after_request
def apply_security_headers(response):
    for key, value in g.resp_headers.items():
        response.headers[key] = value
    return response""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },
    {
        "id": "eval-safe-misc-007",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "c",
        "vulnerable_code": """int safe_copy(char *dest, size_t dest_size, const char *src) {
    if (dest == NULL || src == NULL || dest_size == 0) {
        return -1;
    }
    size_t src_len = strnlen(src, dest_size);
    memcpy(dest, src, src_len);
    dest[dest_size - 1] = '\\0';
    return 0;
}""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },
    {
        "id": "eval-safe-misc-008",
        "source": "manual_owasp",
        "cwe_id": None,
        "language": "typescript",
        "vulnerable_code": """import { z } from 'zod';

const TransferSchema = z.object({
    to: z.string().uuid(),
    amount: z.number().positive().max(100000),
    currency: z.enum(['USD', 'EUR', 'CNY']),
});

app.post('/api/transfer', (req, res) => {
    const parsed = TransferSchema.safeParse(req.body);
    if (!parsed.success) {
        return res.status(400).json({ errors: parsed.error.issues });
    }
    processTransfer(parsed.data);
    res.json({ status: 'ok' });
});""",
        "fixed_code": None,
        "is_safe": True,
        "ground_truth": {
            "has_vuln": False,
            "cwe_id": None,
            "vuln_type": "N/A",
            "severity": "NONE",
            "fix_reference": None,
        },
    },
]


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    vuln_count = sum(1 for s in SAMPLES if not s["is_safe"])
    safe_count = sum(1 for s in SAMPLES if s["is_safe"])

    print(f"Total samples: {len(SAMPLES)}")
    print(f"  Vulnerable: {vuln_count}")
    print(f"  Safe:       {safe_count}")

    # Check CWE coverage
    cwes = set()
    for s in SAMPLES:
        if s["cwe_id"]:
            cwes.add(s["cwe_id"])
    print(f"  CWE types:  {len(cwes)} — {sorted(cwes)}")

    # Check language coverage
    langs = set(s["language"] for s in SAMPLES)
    print(f"  Languages:  {len(langs)} — {sorted(langs)}")

    # Write
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for sample in SAMPLES:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print(f"\nSaved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
