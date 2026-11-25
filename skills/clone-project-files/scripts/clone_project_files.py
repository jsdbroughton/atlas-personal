#!/usr/bin/env python3
"""
Cross-server Speckle project file transfer via public APIs (reingest).

Primary job: copy or move files between any Speckle hosts — local, staging/next,
or production — without DB/S3 cloning. New document ids on the target.

Modes:
  clone — copy selected file versions into the target (new document ids)
  move  — cross-server only: clone then soft-delete verified source documents.
          Same-server move refused (use packages/server/scripts/move/).

Defaults: --mode clone; --versions latest for clone, all for move
(when --versions omitted).

Version depth (--versions):
  latest  — highest versionNumber only (clone default)
  all     — every version, oldest → newest (move default)
  <N>     — N most recent, then upload oldest → newest among that set

Credentials: environment variables only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

# Cloudflare on app.speckle.systems answers the default Python-urllib UA with 403/1010.
_BaseRequest = Request


class Request(_BaseRequest):  # noqa: N801
  def __init__(self, *a, **kw):  # noqa: ANN002, ANN003
    super().__init__(*a, **kw)
    if not self.has_header('User-agent'):
      self.add_header('User-Agent', 'speckle-clone-project-files/1.0')

TABULAR_EXT = {'.csv', '.xlsx', '.xls'}
RVT_EXT = {'.rvt'}


class NoRedirect(HTTPRedirectHandler):
  def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
    return None


def die(msg: str, code: int = 1) -> None:
  print(f'error: {msg}', file=sys.stderr)
  raise SystemExit(code)


def env(name: str, required: bool = True) -> str | None:
  value = os.environ.get(name)
  if required and (value is None or value.strip() == ''):
    die(f'missing env {name}')
  return value.strip() if value else None


def normalize_origin(origin: str) -> str:
  parsed = urlparse(origin.strip())
  if not parsed.scheme or not parsed.netloc:
    die(f'invalid origin: {origin}')
  host = parsed.netloc.lower()
  if host.endswith(':80') and parsed.scheme == 'http':
    host = host[:-3]
  if host.endswith(':443') and parsed.scheme == 'https':
    host = host[:-4]
  return f'{parsed.scheme.lower()}://{host}'


def same_server(a: str, b: str) -> bool:
  return normalize_origin(a) == normalize_origin(b)


def gql(
  origin: str,
  token: str,
  query: str,
  variables: dict[str, Any] | None = None,
  timeout: int = 120,
) -> dict[str, Any]:
  req = Request(
    f'{origin.rstrip("/")}/graphql',
    data=json.dumps({'query': query, 'variables': variables or {}}).encode(),
    headers={
      'Content-Type': 'application/json',
      'Authorization': f'Bearer {token}',
    },
    method='POST',
  )
  try:
    with urlopen(req, timeout=timeout) as res:
      body = json.load(res)
  except HTTPError as e:
    raw = e.read().decode(errors='replace')
    try:
      body = json.loads(raw)
    except json.JSONDecodeError:
      die(f'HTTP {e.code} from {origin}: {raw[:400]}')
  if body.get('errors'):
    die(json.dumps(body['errors'])[:1200])
  data = body.get('data')
  if data is None:
    die(f'empty GraphQL data from {origin}: {json.dumps(body)[:400]}')
  return data


def gql_or_none(
  origin: str,
  token: str,
  query: str,
  variables: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
  req = Request(
    f'{origin.rstrip("/")}/graphql',
    data=json.dumps({'query': query, 'variables': variables or {}}).encode(),
    headers={
      'Content-Type': 'application/json',
      'Authorization': f'Bearer {token}',
    },
    method='POST',
  )
  try:
    with urlopen(req, timeout=120) as res:
      body = json.load(res)
  except HTTPError as e:
    try:
      body = json.loads(e.read().decode(errors='replace'))
    except json.JSONDecodeError:
      return None
  if body.get('errors'):
    return None
  return body.get('data')


def login_token(origin: str, email: str, password: str, app_id: str) -> str:
  challenge = uuid.uuid4().hex
  opener = build_opener(NoRedirect)
  login_req = Request(
    f'{origin.rstrip("/")}/auth/local/login?challenge={challenge}',
    data=json.dumps({'email': email, 'password': password}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST',
  )
  try:
    opener.open(login_req, timeout=30)
    die('login returned 2xx without redirect')
  except HTTPError as e:
    loc = e.headers.get('Location') or e.headers.get('location')
    if not loc:
      die(f'login failed HTTP {e.code}: {e.read()[:300]!r}')
    access_code = parse_qs(urlparse(loc).query).get('access_code', [None])[0]
    if not access_code:
      die(f'no access_code in login redirect: {loc}')
  tok_req = Request(
    f'{origin.rstrip("/")}/auth/token',
    data=json.dumps(
      {
        'appId': app_id,
        'appSecret': app_id,
        'accessCode': access_code,
        'challenge': challenge,
      }
    ).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST',
  )
  with urlopen(tok_req, timeout=30) as res:
    body = json.load(res)
  token = body.get('token')
  if not token:
    die(f'token exchange failed: {json.dumps(body)[:300]}')
  return token


def resolve_token(
  origin: str,
  token_env: str | None,
  email_env: str,
  password_env: str,
  app_id: str,
) -> str:
  if token_env:
    token = env(token_env)
    assert token
    return token
  email = env(email_env)
  password = env(password_env)
  assert email and password
  return login_token(origin, email, password, app_id)


def normalize_doc(item: dict[str, Any]) -> dict[str, Any]:
  versions = item.get('versions') or []
  if isinstance(versions, dict):
    versions = versions.get('items') or []
  versions = sorted(versions, key=lambda v: v.get('versionNumber') or 0)
  return {
    'id': item['id'],
    'name': item['name'],
    'type': item.get('type'),
    'mimeType': item.get('mimeType'),
    'versionCount': item.get('versionCount') or len(versions),
    'currentVersionId': item.get('currentVersionId'),
    'versions': versions,
  }


def order_versions(versions: list[dict[str, Any]]) -> list[dict[str, Any]]:
  """Canonical order: versionNumber ascending (unique); refuse duplicate numbers."""
  nums = [v.get('versionNumber') for v in versions]
  if len(nums) != len(set(nums)):
    die('source document has duplicate versionNumber values; refuse ambiguous ordering')
  return sorted(versions, key=lambda v: v.get('versionNumber') or 0)


def select_versions(
  versions: list[dict[str, Any]],
  depth: str,
  *,
  current_version_id: str | None,
) -> list[dict[str, Any]]:
  """Return versions oldest→newest for upload, filtered by depth."""
  ordered = order_versions(versions)
  if not ordered:
    return []
  if depth == 'all':
    return ordered
  if depth == 'latest':
    highest = ordered[-1]
    if current_version_id and current_version_id != highest.get('id'):
      current = next((v for v in ordered if v.get('id') == current_version_id), None)
      if current is None:
        die(
          f'currentVersionId {current_version_id} missing from versions list'
        )
      die(
        f'latest ambiguous: currentVersionId is v{current.get("versionNumber")} '
        f'but highest versionNumber is v{highest.get("versionNumber")}; '
        'resolve on source or pass --versions all|N'
      )
    return [highest]
  n = int(depth)
  if n < 1:
    die('--versions N must be >= 1')
  if n > len(ordered):
    print(
      f'note: --versions {n} > {len(ordered)} available; using all {len(ordered)}',
      file=sys.stderr,
    )
    selected = ordered
  else:
    selected = ordered[-n:]
  if current_version_id and current_version_id not in {v.get('id') for v in selected}:
    current = next((v for v in ordered if v.get('id') == current_version_id), None)
    cur_n = current.get('versionNumber') if current else '?'
    die(
      f'--versions {n} excludes currentVersionId (v{cur_n}); '
      'raise N, use --versions all, or resolve current on source'
    )
  return selected


def parse_versions_arg(value: str) -> str:
  v = value.strip().lower()
  if v in ('all', 'latest'):
    return v
  if v.isdigit() and int(v) >= 1:
    return v
  die("--versions must be 'all', 'latest', or a positive integer (≥1)")


def inventory_documents(origin: str, token: str, project_id: str) -> list[dict[str, Any]]:
  by_id: dict[str, dict[str, Any]] = {}

  def add_items(items: list[dict[str, Any]]) -> None:
    for item in items:
      if item.get('type') == 'folder':
        continue
      by_id[item['id']] = normalize_doc(item)

  cursor: str | None = None
  while True:
    data = gql_or_none(
      origin,
      token,
      '''
      query($id: String!, $cursor: String) {
        project(id: $id) {
          documentPage(
            parentId: null
            filter: { extensions: ["csv", "xlsx", "xls", "rvt"] }
            limit: 100
            cursor: $cursor
          ) {
            totalCount
            cursor
            items {
              id name type mimeType versionCount currentVersionId
              versions(limit: 100) {
                id versionNumber sizeBytes createdAt downloadUrl
              }
            }
          }
        }
      }
      ''',
      {'id': project_id, 'cursor': cursor},
    )
    if data is None:
      break
    page = data['project']['documentPage']
    add_items(page['items'])
    cursor = page.get('cursor')
    if not cursor or len(page['items']) == 0:
      break
    if page.get('totalCount') is not None and len(by_id) >= page['totalCount']:
      break

  data = gql_or_none(
    origin,
    token,
    '''
    query($id: String!) {
      project(id: $id) {
        recentDocuments(limit: 200) {
          id name type mimeType versionCount currentVersionId
          versions(limit: 100) {
            id versionNumber sizeBytes createdAt downloadUrl
          }
        }
      }
    }
    ''',
    {'id': project_id},
  )
  if data is None:
    data = gql(
      origin,
      token,
      '''
      query($id: String!) {
        project(id: $id) {
          recentDocuments(limit: 200) {
            id name type mimeType versionCount currentVersionId
            versions {
              id versionNumber sizeBytes createdAt downloadUrl
            }
          }
        }
      }
      ''',
      {'id': project_id},
    )
  items = data['project']['recentDocuments']
  if len(items) >= 200:
    print(
      'warn: recentDocuments hit 200 — inventory may be incomplete',
      file=sys.stderr,
    )
  add_items(items)
  return sorted(by_id.values(), key=lambda d: d['name'])


def fetch_document(
  origin: str, token: str, project_id: str, document_id: str
) -> dict[str, Any] | None:
  data = gql_or_none(
    origin,
    token,
    '''
    query($p: String!, $id: String!) {
      project(id: $p) {
        document(id: $id) {
          id name type mimeType versionCount currentVersionId
          versions(limit: 100) {
            id versionNumber sizeBytes createdAt downloadUrl
          }
        }
      }
    }
    ''',
    {'p': project_id, 'id': document_id},
  )
  if data is None:
    data = gql_or_none(
      origin,
      token,
      '''
      query($p: String!, $id: String!) {
        project(id: $p) {
          document(id: $id) {
            id name type mimeType versionCount currentVersionId
            versions {
              id versionNumber sizeBytes createdAt downloadUrl
            }
          }
        }
      }
      ''',
      {'p': project_id, 'id': document_id},
    )
  if not data or not data['project'].get('document'):
    return None
  return normalize_doc(data['project']['document'])


def resolve_file_docs(
  *,
  origin: str,
  token: str,
  project_id: str,
  inventory: list[dict[str, Any]],
  file_ref: str,
) -> list[dict[str, Any]]:
  by_id = fetch_document(origin, token, project_id, file_ref)
  if by_id:
    return [by_id]
  exact = [d for d in inventory if d['name'] == file_ref]
  if len(exact) == 1:
    return exact
  if len(exact) > 1:
    die(f'multiple documents named exactly {file_ref!r}; use document id')
  die(f'no document id or exact name match for --source-file {file_ref!r}')


def resolve_model_docs(
  *,
  origin: str,
  token: str,
  project_id: str,
  model_ref: str,
) -> list[dict[str, Any]]:
  """Model id or exact name → sourceDocument (and document if distinct)."""
  data = gql_or_none(
    origin,
    token,
    '''
    query($p: String!, $id: String!) {
      project(id: $p) {
        model(id: $id) {
          id name
          sourceDocument {
            id name type mimeType versionCount currentVersionId
            versions(limit: 100) {
              id versionNumber sizeBytes createdAt downloadUrl
            }
          }
          document {
            id name type mimeType versionCount currentVersionId
            versions(limit: 100) {
              id versionNumber sizeBytes createdAt downloadUrl
            }
          }
        }
      }
    }
    ''',
    {'p': project_id, 'id': model_ref},
  )
  model = data['project']['model'] if data else None
  if model is None:
    data = gql_or_none(
      origin,
      token,
      '''
      query($p: String!, $name: String!) {
        project(id: $p) {
          modelByName(name: $name) {
            id name
            sourceDocument {
              id name type mimeType versionCount currentVersionId
              versions(limit: 100) {
                id versionNumber sizeBytes createdAt downloadUrl
              }
            }
            document {
              id name type mimeType versionCount currentVersionId
              versions(limit: 100) {
                id versionNumber sizeBytes createdAt downloadUrl
              }
            }
          }
        }
      }
      ''',
      {'p': project_id, 'name': model_ref},
    )
    model = data['project'].get('modelByName') if data else None

  if model is None:
    # exact name among models list
    listed = gql(
      origin,
      token,
      '''
      query($p: String!) {
        project(id: $p) {
          models(limit: 100) {
            items { id name }
          }
        }
      }
      ''',
      {'p': project_id},
    )
    matches = [m for m in listed['project']['models']['items'] if m['name'] == model_ref]
    if len(matches) > 1:
      die(f'multiple models named exactly {model_ref!r}; use model id')
    if len(matches) == 0:
      die(f'no model id or exact name match for --source-model {model_ref!r}')
    return resolve_model_docs(
      origin=origin, token=token, project_id=project_id, model_ref=matches[0]['id']
    )

  docs: dict[str, dict[str, Any]] = {}
  for key in ('sourceDocument', 'document'):
    raw = model.get(key)
    if not raw:
      continue
    # versions may be list or missing on nested fetch — re-fetch full doc
    full = fetch_document(origin, token, project_id, raw['id'])
    if full:
      docs[full['id']] = full
  if not docs:
    die(
      f'model {model_ref!r} ({model["id"]}) has no sourceDocument/document file to transfer'
    )
  return list(docs.values())


def create_project(
  origin: str, token: str, workspace_id: str, name: str
) -> dict[str, Any]:
  data = gql(
    origin,
    token,
    '''
    mutation($input: ProjectCreateInput!) {
      projectMutations { create(input: $input) { id name workspaceId } }
    }
    ''',
    {'input': {'name': name, 'workspaceId': workspace_id}},
  )
  return data['projectMutations']['create']


def soft_delete_document(
  origin: str, token: str, project_id: str, document_id: str
) -> None:
  gql(
    origin,
    token,
    '''
    mutation($input: DocumentIdInput!) {
      projectMutations { documents { delete(input: $input) { id } } }
    }
    ''',
    {'input': {'projectId': project_id, 'documentId': document_id}},
  )


def load_id_map(path: Path) -> dict[str, Any]:
  if path.exists():
    return json.loads(path.read_text())
  return {
    'source': {},
    'target': {},
    'tabular': {},
    'blobs': {},
    'deletedSource': {},
    'notes': [],
  }


def save_id_map(path: Path, data: dict[str, Any]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(data, indent=2) + '\n')


def download(url: str, dest: Path) -> None:
  dest.parent.mkdir(parents=True, exist_ok=True)
  __import__('urllib.request').request.urlretrieve(url, dest)


def sha256_file(path: Path) -> str:
  h = hashlib.sha256()
  with path.open('rb') as f:
    for chunk in iter(lambda: f.read(1024 * 1024), b''):
      h.update(chunk)
  return h.hexdigest()


def upload_data_source(
  *,
  api_origin: str,
  token: str,
  workspace_id: str,
  project_id: str,
  path: Path,
  name: str,
  replace_of: str | None,
) -> dict[str, Any]:
  boundary = '----clone' + uuid.uuid4().hex
  data = path.read_bytes()
  mime = (
    'text/csv'
    if path.suffix.lower() == '.csv'
    else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  )
  body = (
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
    f'Content-Type: {mime}\r\n\r\n'
  ).encode() + data + f'\r\n--{boundary}--\r\n'.encode()
  qs = f'source=upload&projectId={project_id}'
  if replace_of:
    qs += f'&replaceOf={replace_of}'
  req = Request(
    f'{api_origin.rstrip("/")}/api/workspaces/{workspace_id}/data-sources?{qs}',
    data=body,
    headers={
      'Authorization': f'Bearer {token}',
      'Content-Type': f'multipart/form-data; boundary={boundary}',
    },
    method='POST',
  )
  try:
    with urlopen(req, timeout=300) as res:
      return {'status': res.status, 'body': json.load(res)}
  except HTTPError as e:
    die(f'data-sources upload HTTP {e.code}: {e.read()[:500]}')


def wait_eds_ready(
  origin: str, token: str, project_id: str, file_id: str, timeout_s: float = 90
) -> dict[str, Any]:
  deadline = time.time() + timeout_s
  while time.time() < deadline:
    data = gql(
      origin,
      token,
      '''
      query($p: String!, $id: String!) {
        project(id: $p) {
          externalDataSource(id: $id) { id name status }
        }
      }
      ''',
      {'p': project_id, 'id': file_id},
    )
    src = data['project']['externalDataSource']
    if src and src.get('status') == 'ready':
      return src
    time.sleep(0.25)
  die(f'timed out waiting for externalDataSource {file_id} ready')


def upload_blob(
  *,
  blob_origin: str,
  token: str,
  project_id: str,
  path: Path,
) -> str:
  boundary = '----blob' + uuid.uuid4().hex
  data = path.read_bytes()
  body = (
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
    f'Content-Type: application/octet-stream\r\n\r\n'
  ).encode() + data + f'\r\n--{boundary}--\r\n'.encode()
  req = Request(
    f'{blob_origin.rstrip("/")}/api/stream/{project_id}/blob',
    data=body,
    headers={
      'Authorization': f'Bearer {token}',
      'Content-Type': f'multipart/form-data; boundary={boundary}',
    },
    method='POST',
  )
  try:
    with urlopen(req, timeout=600) as res:
      out = json.load(res)
  except HTTPError as e:
    die(
      f'blob upload HTTP {e.code} via {blob_origin}: {e.read()[:400]} '
      f'(try --blob-origin if nginx body limit is too small)'
    )
  results = out.get('uploadResults') or out
  blob = results[0].get('blobId') if isinstance(results, list) else out.get('blobId')
  if not blob:
    die(f'no blobId in upload response: {json.dumps(out)[:300]}')
  return blob


def create_document(
  origin: str, token: str, project_id: str, name: str, blob_id: str
) -> dict[str, Any]:
  data = gql(
    origin,
    token,
    '''
    mutation($input: DocumentCreateInput!) {
      projectMutations {
        documents {
          create(input: $input) { id name versionCount currentVersionId }
        }
      }
    }
    ''',
    {
      'input': {
        'projectId': project_id,
        'name': name,
        'blobId': blob_id,
        'mimeType': 'application/octet-stream',
        'source': 'clone-project-files',
      }
    },
  )
  return data['projectMutations']['documents']['create']


def replace_document(
  origin: str, token: str, project_id: str, document_id: str, blob_id: str, comment: str
) -> dict[str, Any]:
  data = gql(
    origin,
    token,
    '''
    mutation($input: DocumentReplaceContentInput!) {
      projectMutations {
        documents {
          replaceContent(input: $input) { id name versionCount currentVersionId }
        }
      }
    }
    ''',
    {
      'input': {
        'projectId': project_id,
        'documentId': document_id,
        'blobId': blob_id,
        'comment': comment,
        'source': 'clone-project-files',
      }
    },
  )
  return data['projectMutations']['documents']['replaceContent']


def doc_fully_verified(
  entry: dict[str, Any], selected_version_ids: list[str]
) -> bool:
  versions = entry.get('versions') or {}
  if not selected_version_ids:
    return False
  return all(versions.get(vid, {}).get('ok') for vid in selected_version_ids)


def parse_args() -> argparse.Namespace:
  p = argparse.ArgumentParser(
    description='Clone/move Speckle project files via API reingest'
  )
  p.add_argument('--mode', choices=('clone', 'move'), default='clone')
  p.add_argument('--source-origin', required=True)
  p.add_argument(
    '--target-origin',
    default=None,
    help='target host (local/staging/production). Default: --source-origin',
  )
  p.add_argument('--source-project', required=True)
  p.add_argument(
    '--source-model',
    default=None,
    help='model id or exact name — transfer its source file document(s) only',
  )
  p.add_argument(
    '--source-file',
    default=None,
    help='document id or exact file name — transfer that file only',
  )
  p.add_argument(
    '--source-token-env',
    default='SPECKLE_NEXT_TOKEN',
    help='source bearer env (or use SOURCE_EMAIL/SOURCE_PASSWORD)',
  )
  p.add_argument('--blob-origin', default=None)
  p.add_argument('--target-project', default=None)
  p.add_argument(
    '--create-project-name',
    default=None,
    help='create target project with this name when --target-project omitted',
  )
  p.add_argument(
    '--target-workspace',
    required=True,
    help='workspace id (data-sources + project create)',
  )
  p.add_argument('--target-token-env', default=None)
  p.add_argument('--auth-app-id', default='spklwebapp')
  p.add_argument('--artefacts-dir', required=True, type=Path)
  p.add_argument(
    '--versions',
    default=None,
    help="all | latest | N (N most recent). Default: latest for clone, all for move",
  )
  p.add_argument('--tabular-only', action='store_true')
  p.add_argument('--include-rvt', action='store_true')
  p.add_argument('--inventory-only', action='store_true')
  p.add_argument(
    '--dry-run',
    action='store_true',
    help='list planned transfers; no create/upload/delete',
  )
  p.add_argument(
    '--force',
    action='store_true',
    help='required for move delete when stdin is not a TTY',
  )
  p.add_argument(
    '--discard-older-versions',
    action='store_true',
    help='required with --mode move when --versions is not all (deletes unselected history)',
  )
  p.add_argument(
    '--delete-source-only',
    action='store_true',
    help='move resume: skip clone; soft-delete source docs already verified in id-map',
  )
  return p.parse_args()


def main() -> None:
  args = parse_args()
  if args.versions is None:
    versions_depth = 'all' if args.mode == 'move' else 'latest'
  else:
    versions_depth = parse_versions_arg(args.versions)
  source_origin = args.source_origin.rstrip('/')
  target_origin = (args.target_origin or args.source_origin).rstrip('/')
  blob_origin = (args.blob_origin or target_origin).rstrip('/')

  if args.source_model and args.source_file:
    die('pass only one of --source-model or --source-file')

  if args.mode == 'move' and same_server(source_origin, target_origin):
    die(
      'same-server move refused. Use packages/server/scripts/move/ '
      '(keeps ids). This tool only moves cross-server (clone then soft-delete).'
    )

  if (
    args.target_project
    and args.target_project == args.source_project
    and same_server(source_origin, target_origin)
  ):
    die('source and target are the same project')

  # Source auth: token env, else SOURCE_EMAIL/PASSWORD, else same as TARGET for same-server
  if os.environ.get(args.source_token_env):
    source_token = env(args.source_token_env)
  elif os.environ.get('SOURCE_EMAIL'):
    source_token = resolve_token(
      source_origin, None, 'SOURCE_EMAIL', 'SOURCE_PASSWORD', args.auth_app_id
    )
  elif same_server(source_origin, target_origin):
    source_token = None  # fill after target login
  else:
    source_token = env(args.source_token_env)

  artefacts: Path = args.artefacts_dir
  artefacts.mkdir(parents=True, exist_ok=True)
  id_map_path = artefacts / 'id-map.json'
  id_map = load_id_map(id_map_path)

  if source_token is None:
    # defer until target token known
    pass
  else:
    assert source_token

  # Early inventory needs source token
  if source_token is None:
    if args.target_token_env:
      shared = env(args.target_token_env)
    else:
      shared = resolve_token(
        target_origin,
        None,
        'TARGET_EMAIL',
        'TARGET_PASSWORD',
        args.auth_app_id,
      )
    source_token = shared
    target_token_early = shared
  else:
    target_token_early = None

  assert source_token

  print('inventory…')
  inventory = inventory_documents(source_origin, source_token, args.source_project)

  if args.source_model:
    docs = resolve_model_docs(
      origin=source_origin,
      token=source_token,
      project_id=args.source_project,
      model_ref=args.source_model,
    )
  elif args.source_file:
    docs = resolve_file_docs(
      origin=source_origin,
      token=source_token,
      project_id=args.source_project,
      inventory=inventory,
      file_ref=args.source_file,
    )
  else:
    docs = inventory

  # apply version depth for planning
  planned: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
  discarded_total = 0
  for doc in docs:
    selected = select_versions(
      doc['versions'],
      versions_depth,
      current_version_id=doc.get('currentVersionId'),
    )
    discarded_total += max(0, len(doc['versions']) - len(selected))
    planned.append((doc, selected))

  if args.mode == 'move' and versions_depth != 'all' and discarded_total > 0:
    msg = (
      f'move with --versions {versions_depth} would soft-delete source docs and '
      f'discard {discarded_total} unselected version(s) of history'
    )
    if not args.discard_older_versions:
      die(f'{msg}. Pass --discard-older-versions to acknowledge, or use --versions all')
    print(f'warn: {msg}', file=sys.stderr)

  # resume: refuse depth / selection mismatch vs existing id-map
  has_progress = bool(
    id_map.get('tabular')
    or id_map.get('blobs')
    or id_map.get('deletedSource')
    or id_map.get('selectedVersionIdsByDoc')
    or id_map.get('versions')
  )
  if has_progress and 'versions' not in id_map:
    die(
      'legacy id-map missing versions field; use a fresh --artefacts-dir '
      '(or re-run once with matching --versions after upgrading the skill)'
    )
  if id_map.get('versions') is not None and id_map['versions'] != versions_depth:
    die(
      f'id-map versions={id_map["versions"]!r} != --versions {versions_depth!r}; '
      'use a fresh --artefacts-dir or match the prior depth'
    )
  prior_sel = id_map.get('selectedVersionIdsByDoc')
  if has_progress and prior_sel is None and id_map.get('versions') is not None:
    die(
      'legacy id-map missing selectedVersionIdsByDoc; use a fresh --artefacts-dir'
    )
  prior_sel = prior_sel or {}
  for doc, selected in planned:
    ids = [v['id'] for v in selected]
    if doc['id'] in prior_sel and prior_sel[doc['id']] != ids:
      die(
        f'id-map selected versions for {doc["name"]} differ from this run; '
        'use a fresh --artefacts-dir or the same --versions / scope'
      )

  inv_path = artefacts / 'inventory.json'
  inv_path.write_text(
    json.dumps(
      {
        'mode': args.mode,
        'versions': versions_depth,
        'discardedUnselectedVersions': discarded_total,
        'documents': [
          {
            **{k: d[k] for k in d if k != 'versions'},
            'selectedVersionIds': [v['id'] for v in selected],
            'unselectedVersionCount': len(d['versions']) - len(selected),
            'versions': [
              {k: v[k] for k in v if k != 'downloadUrl'} for v in selected
            ],
          }
          for d, selected in planned
        ],
      },
      indent=2,
    )
    + '\n'
  )
  print(f'  {len(planned)} document(s), versions={versions_depth} → {inv_path}')
  for doc, selected in planned:
    nums = [v.get('versionNumber') for v in selected]
    skipped = len(doc['versions']) - len(selected)
    extra = f' (discard {skipped} older)' if skipped else ''
    print(f"    {doc['name']} versions={nums}{extra}")

  if args.dry_run or args.inventory_only:
    if args.dry_run:
      print('dry-run: no create/upload/delete')
    save_id_map(id_map_path, id_map)
    return

  if target_token_early is not None:
    target_token = target_token_early
  elif args.target_token_env:
    target_token = env(args.target_token_env)
  else:
    target_token = resolve_token(
      target_origin, None, 'TARGET_EMAIL', 'TARGET_PASSWORD', args.auth_app_id
    )
  assert target_token

  target_project = args.target_project
  if not target_project:
    if not args.create_project_name:
      die('pass --target-project or --create-project-name')
    created = create_project(
      target_origin, target_token, args.target_workspace, args.create_project_name
    )
    target_project = created['id']
    print(f'created project {target_project} {created.get("name")}')
    id_map.setdefault('notes', []).append(f'createdProject:{target_project}')

  id_map['source'] = {
    'origin': normalize_origin(source_origin),
    'projectId': args.source_project,
  }
  id_map['target'] = {
    'origin': normalize_origin(target_origin),
    'blobOrigin': blob_origin,
    'projectId': target_project,
    'workspaceId': args.target_workspace,
  }
  id_map['versions'] = versions_depth
  id_map['selectedVersionIdsByDoc'] = {
    doc['id']: [v['id'] for v in selected] for doc, selected in planned
  }
  save_id_map(id_map_path, id_map)

  if args.delete_source_only:
    if args.mode != 'move':
      die('--delete-source-only only with --mode move')
    # Two-step move: clone first, delete later — still require discard ack
    # when this run (or prior id-map) used partial depth with unselected history.
    map_depth = id_map.get('versions') or versions_depth
    if map_depth != 'all' and discarded_total > 0 and not args.discard_older_versions:
      die(
        f'--delete-source-only with --versions {map_depth} would drop '
        f'{discarded_total} unselected source version(s). '
        'Pass --discard-older-versions, or use --versions all'
      )
    _delete_verified_sources(
      args=args,
      source_origin=source_origin,
      source_token=source_token,
      target_origin=target_origin,
      target_token=target_token,
      target_project=target_project,
      planned=planned,
      id_map=id_map,
      id_map_path=id_map_path,
    )
    return

  # classify
  to_transfer: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
  for doc, selected in planned:
    ext = Path(doc['name']).suffix.lower()
    if ext in TABULAR_EXT:
      to_transfer.append((doc, selected))
    elif ext in RVT_EXT:
      if args.tabular_only and not args.include_rvt:
        print(f'  skip rvt {doc["name"]} (tabular-only)', file=sys.stderr)
        continue
      if not args.include_rvt and not args.source_model and not args.source_file:
        # whole-project default: need --include-rvt
        print(f'  skip rvt {doc["name"]} (pass --include-rvt)', file=sys.stderr)
        continue
      to_transfer.append((doc, selected))
    else:
      # other binary via blob path when explicitly scoped
      if args.source_model or args.source_file:
        to_transfer.append((doc, selected))
      else:
        print(f'  skip unsupported {doc["name"]}', file=sys.stderr)

  for doc, selected in to_transfer:
    ext = Path(doc['name']).suffix.lower()
    if ext in TABULAR_EXT:
      _transfer_tabular(
        doc=doc,
        selected=selected,
        args=args,
        target_origin=target_origin,
        target_token=target_token,
        target_project=target_project,
        artefacts=artefacts,
        id_map=id_map,
        id_map_path=id_map_path,
      )
    else:
      _transfer_blob(
        doc=doc,
        selected=selected,
        args=args,
        target_origin=target_origin,
        blob_origin=blob_origin,
        target_token=target_token,
        target_project=target_project,
        artefacts=artefacts,
        id_map=id_map,
        id_map_path=id_map_path,
      )

  if args.mode == 'move':
    _delete_verified_sources(
      args=args,
      source_origin=source_origin,
      source_token=source_token,
      target_origin=target_origin,
      target_token=target_token,
      target_project=target_project,
      planned=to_transfer,
      id_map=id_map,
      id_map_path=id_map_path,
    )

  save_id_map(id_map_path, id_map)
  print(f'done → {id_map_path}')


def _transfer_tabular(
  *,
  doc: dict[str, Any],
  selected: list[dict[str, Any]],
  args: argparse.Namespace,
  source_origin: str,
  target_origin: str,
  target_token: str,
  target_project: str,
  artefacts: Path,
  id_map: dict[str, Any],
  id_map_path: Path,
) -> None:
  entry = id_map.setdefault('tabular', {}).setdefault(
    doc['id'],
    {'name': doc['name'], 'targetFileId': None, 'versions': {}, 'selectedVersionIds': []},
  )
  entry['selectedVersionIds'] = [v['id'] for v in selected]
  target_file_id: str | None = entry.get('targetFileId')
  for ver in selected:
    vid = ver['id']
    if entry['versions'].get(vid, {}).get('ok'):
      print(f'  skip tabular {doc["name"]} v{ver["versionNumber"]} (id-map)')
      target_file_id = entry['targetFileId'] or entry['versions'][vid].get(
        'targetFileId'
      )
      continue
    url = ver.get('downloadUrl')
    if not url:
      die(f'no downloadUrl for {doc["name"]} {vid}')
    dest = (
      artefacts
      / 'download'
      / 'tabular'
      / doc['id']
      / f'v{ver["versionNumber"]}-{vid}{Path(doc["name"]).suffix.lower()}'
    )
    if not dest.exists() or dest.stat().st_size != ver.get('sizeBytes'):
      print(f'  download {doc["name"]} v{ver["versionNumber"]}')
      download(url, dest)
    print(f'  upload tabular {doc["name"]} v{ver["versionNumber"]}')
    status_body = upload_data_source(
      api_origin=target_origin,
      token=target_token,
      workspace_id=args.target_workspace,
      project_id=target_project,
      path=dest,
      name=doc['name'],
      replace_of=target_file_id,
    )
    body = status_body['body']
    target_file_id = body['id']
    wait_eds_ready(target_origin, target_token, target_project, target_file_id)
    entry['targetFileId'] = target_file_id
    entry['versions'][vid] = {
      'sourceVersionNumber': ver['versionNumber'],
      'targetFileId': target_file_id,
      'sha256': sha256_file(dest),
      'bytes': dest.stat().st_size,
      'ok': True,
    }
    save_id_map(id_map_path, id_map)


def _transfer_blob(
  *,
  doc: dict[str, Any],
  selected: list[dict[str, Any]],
  args: argparse.Namespace,
  target_origin: str,
  blob_origin: str,
  target_token: str,
  target_project: str,
  artefacts: Path,
  id_map: dict[str, Any],
  id_map_path: Path,
) -> None:
  entry = id_map.setdefault('blobs', {}).setdefault(
    doc['id'],
    {'name': doc['name'], 'targetDocId': None, 'versions': {}, 'selectedVersionIds': []},
  )
  entry['selectedVersionIds'] = [v['id'] for v in selected]
  target_doc_id: str | None = entry.get('targetDocId')
  for ver in selected:
    vid = ver['id']
    if entry['versions'].get(vid, {}).get('ok'):
      print(f'  skip blob {doc["name"]} v{ver["versionNumber"]} (id-map)')
      target_doc_id = entry['targetDocId'] or entry['versions'][vid].get('targetDocId')
      continue
    url = ver.get('downloadUrl')
    if not url:
      die(f'no downloadUrl for {doc["name"]} {vid}')
    suffix = Path(doc['name']).suffix.lower() or '.bin'
    dest = (
      artefacts
      / 'download'
      / 'blobs'
      / doc['id']
      / f'v{ver["versionNumber"]}-{vid}{suffix}'
    )
    if not dest.exists() or dest.stat().st_size != ver.get('sizeBytes'):
      print(f'  download {doc["name"]} v{ver["versionNumber"]}')
      download(url, dest)
    print(f'  upload blob {doc["name"]} v{ver["versionNumber"]}')
    blob_id = upload_blob(
      blob_origin=blob_origin,
      token=target_token,
      project_id=target_project,
      path=dest,
    )
    if target_doc_id is None:
      created = create_document(
        target_origin, target_token, target_project, doc['name'], blob_id
      )
      target_doc_id = created['id']
      target_version_id = created['currentVersionId']
    else:
      replaced = replace_document(
        target_origin,
        target_token,
        target_project,
        target_doc_id,
        blob_id,
        comment=f'clone v{ver["versionNumber"]}',
      )
      target_version_id = replaced['currentVersionId']
    entry['targetDocId'] = target_doc_id
    entry['versions'][vid] = {
      'sourceVersionNumber': ver['versionNumber'],
      'targetDocId': target_doc_id,
      'targetVersionId': target_version_id,
      'sha256': sha256_file(dest),
      'bytes': dest.stat().st_size,
      'ok': True,
    }
    save_id_map(id_map_path, id_map)


def _live_target_ok(
  *,
  target_origin: str,
  target_token: str,
  target_project: str,
  entry: dict[str, Any],
  kind: str,
  selected_version_ids: list[str],
) -> bool:
  """
  Re-check target has every selected version before source delete.
  Requires live versionCount == len(selected); for blobs also that
  currentVersionId equals the last uploaded targetVersionId in the id-map.
  """
  want = len(selected_version_ids)
  if want < 1:
    return False
  if kind == 'tabular':
    file_id = entry.get('targetFileId')
    if not file_id:
      return False
    data = gql_or_none(
      target_origin,
      target_token,
      '''
      query($p: String!, $id: String!) {
        project(id: $p) {
          externalDataSource(id: $id) { id status versionCount }
        }
      }
      ''',
      {'p': target_project, 'id': file_id},
    )
    src = data['project']['externalDataSource'] if data else None
    if not src or src.get('status') != 'ready':
      return False
    return int(src.get('versionCount') or 0) == want
  doc_id = entry.get('targetDocId')
  if not doc_id:
    return False
  data = gql_or_none(
    target_origin,
    target_token,
    '''
    query($p: String!, $id: String!) {
      project(id: $p) {
        document(id: $id) { id versionCount currentVersionId }
      }
    }
    ''',
    {'p': target_project, 'id': doc_id},
  )
  live = data['project'].get('document') if data else None
  if not live:
    return False
  if int(live.get('versionCount') or 0) != want:
    return False
  last_vid = selected_version_ids[-1]
  expected_current = (entry.get('versions') or {}).get(last_vid, {}).get(
    'targetVersionId'
  )
  if expected_current and live.get('currentVersionId') != expected_current:
    return False
  return True


def _delete_verified_sources(
  *,
  args: argparse.Namespace,
  source_origin: str,
  source_token: str,
  target_origin: str,
  target_token: str,
  target_project: str,
  planned: list[tuple[dict[str, Any], list[dict[str, Any]]]],
  id_map: dict[str, Any],
  id_map_path: Path,
) -> None:
  """
  Soft-delete source documents whose selected versions all verified in id-map
  and whose target mapping still exists live with full version count.
  Leaves source models/versions.
  """
  if not args.force and not sys.stdin.isatty():
    die('move delete requires --force when stdin is not a TTY')
  if sys.stdin.isatty() and not args.force:
    print(
      'About to soft-delete verified source documents (models stay; file links break).',
      file=sys.stderr,
    )
    ans = input('Type DELETE to continue: ').strip()
    if ans != 'DELETE':
      die('aborted')

  deleted = id_map.setdefault('deletedSource', {})
  for doc, selected in planned:
    vids = [v['id'] for v in selected]
    tab = (id_map.get('tabular') or {}).get(doc['id'])
    blob = (id_map.get('blobs') or {}).get(doc['id'])
    entry = tab or blob
    kind = 'tabular' if tab else 'blobs'
    if not entry or not doc_fully_verified(entry, vids):
      print(f'  skip delete {doc["name"]} — not fully verified in id-map', file=sys.stderr)
      continue
    if not _live_target_ok(
      target_origin=target_origin,
      target_token=target_token,
      target_project=target_project,
      entry=entry,
      kind=kind,
      selected_version_ids=vids,
    ):
      print(
        f'  skip delete {doc["name"]} — target missing, not ready, or '
        f'versionCount != {len(vids)} selected',
        file=sys.stderr,
      )
      continue
    if deleted.get(doc['id']):
      print(f'  skip delete {doc["name"]} — already deleted')
      continue
    print(f'  soft-delete source {doc["id"]} {doc["name"]}')
    soft_delete_document(
      source_origin, source_token, args.source_project, doc['id']
    )
    deleted[doc['id']] = {'name': doc['name'], 'ok': True}
    save_id_map(id_map_path, id_map)
  print(
    'note: source models/versions were not deleted — only their source file documents. '
    'Target version numbers are renumbered by upload order (not preserved from source).',
    file=sys.stderr,
  )


if __name__ == '__main__':
  main()
