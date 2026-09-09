# Security Policy

## Supported Versions

Kiwi is under active development. The latest release is the only supported
version. Security fixes are backported to the latest release only.

| Version | Supported |
|---|---|
| Latest release | ✅ |

## Reporting a Vulnerability

Please **do not** open a public issue for security vulnerabilities.

Email the maintainer directly:

- **Taariq Ebrahim** — [taariq@gmail.com](mailto:taariq@gmail.com)

Include as much of the following as possible:

1. The affected version / commit.
2. A clear description of the vulnerability and its impact.
3. Steps to reproduce (a minimal repro script or request is ideal).
4. Any suggested fix, if you have one.

You will receive a response within **5 business days**. Once the issue is
confirmed, a fix will be released as soon as practical and you'll be credited
for the report (unless you prefer to remain anonymous).

## Security Notes for Kiwi

Kiwi is a **local-first** application:

- The FastAPI backend binds to `127.0.0.1` and is intended to be reachable
  only from the local machine.
- All data (archives, index, chat history, bookmarks) stays on your machine.
- Article HTML from ZIM archives is untrusted content and is rendered inside a
  sandboxed `iframe`; the Electron shell has `contextIsolation` enabled,
  `nodeIntegration` disabled, and navigation locked to the local backend.

If you find a way to bypass these boundaries — for example, reading arbitrary
local files through the article endpoints, or escaping the iframe sandbox —
please report it as described above.