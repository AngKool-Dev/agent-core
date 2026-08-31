"""Verify release artifacts."""

import hashlib
import os
import json


def calculate_sha256(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def main():
    dist_dir = 'dist'
    print('Release Artifact Verification')
    print('=' * 70)

    # Check wheel
    wheel_path = os.path.join(dist_dir, 'agentcore-1.0.0-py3-none-any.whl')
    if os.path.exists(wheel_path):
        sha256 = calculate_sha256(wheel_path)
        size = os.path.getsize(wheel_path)
        print(f'Wheel: {wheel_path}')
        print(f'  Size: {size} bytes')
        print(f'  SHA-256: {sha256}')
    else:
        print('Wheel: NOT FOUND')

    # Check sdist
    sdist_path = os.path.join(dist_dir, 'agentcore-1.0.0.tar.gz')
    if os.path.exists(sdist_path):
        sha256 = calculate_sha256(sdist_path)
        size = os.path.getsize(sdist_path)
        print(f'Sdist: {sdist_path}')
        print(f'  Size: {size} bytes')
        print(f'  SHA-256: {sha256}')
    else:
        print('Sdist: NOT FOUND')

    # Check SHA256SUMS
    sha256sums_path = os.path.join(dist_dir, 'SHA256SUMS')
    if os.path.exists(sha256sums_path):
        print(f'SHA256SUMS: {sha256sums_path}')
        with open(sha256sums_path) as f:
            print(f.read())
    else:
        print('SHA256SUMS: NOT FOUND')

    # Check RELEASE_MANIFEST.json
    manifest_path = os.path.join(dist_dir, 'RELEASE_MANIFEST.json')
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)
        print('RELEASE_MANIFEST.json:')
        print(f'  Version: {manifest.get("version")}')
        print(f'  Git revision: {manifest.get("git_revision")}')
        print(f'  Release decision: {manifest.get("release_decision")}')
    else:
        print('RELEASE_MANIFEST.json: NOT FOUND')

    print('=' * 70)
    print('Artifact verification complete')


if __name__ == '__main__':
    main()
