import re
from urllib.parse import urlparse


_MARKDOWN_IMAGE_PATTERN = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')


def extract_upload_filename(url, upload_relative):
    if not url:
        return None
    path = urlparse(url).path or url
    path = path.strip()
    if path.startswith('/'):
        path = path[1:]
    if path.startswith('static/'):
        path = path[len('static/'):]
    upload_relative = (upload_relative or '').strip('/')
    if upload_relative:
        prefix = f"{upload_relative}/"
        if path.startswith(prefix):
            filename = path[len(prefix):]
            return filename or None
    return None


def strip_markdown_images(content, upload_relative, keep_unmatched=True):
    if not content:
        return '', None
    found_filename = None

    def _replace(match):
        nonlocal found_filename
        url = match.group(1).strip()
        filename = extract_upload_filename(url, upload_relative)
        if filename:
            if found_filename is None:
                found_filename = filename
            return ''
        return match.group(0) if keep_unmatched else ''

    cleaned = _MARKDOWN_IMAGE_PATTERN.sub(_replace, content)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
    return cleaned, found_filename
