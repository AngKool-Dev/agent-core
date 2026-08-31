"""Security release audit for GA artifacts - focused on actual secrets."""

import zipfile
import tarfile
import re
import os


# Patterns to search for actual secrets (not examples or patterns)
patterns = {
    'github_token': r'gh[pousr]_[A-Za-z0-9_]{36,}',
    'openai_token': r'sk-[a-zA-Z0-9]{48}',
    'slack_token': r'xox[baprs]-[A-Za-z0-9-]{10,}',
    'aws_key': r'AKIA[0-9A-Z]{16}',
    'private_key': r'-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----',
    'api_key_assignment': r'(?i)(api[_-]?key|apikey|token|secret)\s*[:=]\s*["\'][a-zA-Z0-9_\-]{32,}["\']',
}


def scan_content(content, filename, findings):
    for pattern_name, pattern in patterns.items():
        matches = re.findall(pattern, content)
        if matches:
            for match in matches[:3]:
                findings.append({
                    'file': filename,
                    'pattern': pattern_name,
                    'match': str(match)[:50] + '...' if len(str(match)) > 50 else str(match)
                })


def main():
    # Scan wheel
    wheel_path = 'dist/agentcore-1.0.0-py3-none-any.whl'
    findings = []

    with zipfile.ZipFile(wheel_path, 'r') as zf:
        for info in zf.infolist():
            if info.filename.endswith(('.py', '.txt', '.md', '.toml', '.cfg', '.json', '.yaml', '.yml')):
                try:
                    content = zf.read(info.filename).decode('utf-8', errors='ignore')
                    scan_content(content, info.filename, findings)
                except Exception:
                    pass

    # Scan sdist
    sdist_path = 'dist/agentcore-1.0.0.tar.gz'
    with tarfile.open(sdist_path, 'r:gz') as tf:
        for member in tf.getmembers():
            if member.isfile() and member.name.endswith(('.py', '.txt', '.md', '.toml', '.cfg', '.json', '.yaml', '.yml')):
                try:
                    content = tf.extractfile(member).read().decode('utf-8', errors='ignore')
                    scan_content(content, member.name, findings)
                except Exception:
                    pass

    # Report findings
    print(f'Security scan findings (actual secrets): {len(findings)}')
    for finding in findings[:20]:
        print(f'  {finding["file"]}: {finding["pattern"]} - {finding["match"]}')

    if len(findings) > 20:
        print(f'  ... and {len(findings) - 20} more')

    if len(findings) == 0:
        print('\nGA-003: PASS - No secrets found in release artifacts')
    else:
        print(f'\nGA-003: FAIL - {len(findings)} potential secrets found')


if __name__ == '__main__':
    main()
