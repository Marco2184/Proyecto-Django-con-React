"""Compile existing PO and mirror its messages into the existing React dictionary."""
import ast
import json
from pathlib import Path
from localize_backend import compile_catalog, ROOT

def catalog():
    from gettext_catalog import read_po
    return read_po(ROOT/'locale/en/LC_MESSAGES/django.po')

if __name__=='__main__':
    messages={k.split('\0')[0]:v.split('\0')[0] for k,v in catalog().items() if k}
    if any(not v for v in messages.values()):raise ValueError('Empty translation')
    compile_catalog()
    (ROOT/'frontend/src/serverMessages.js').write_text('// Generated from locale/en/LC_MESSAGES/django.po by docker/sync_i18n.py.\nexport const serverMessages = '+json.dumps(messages,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Compiled and synchronized',len(messages),'server messages')
