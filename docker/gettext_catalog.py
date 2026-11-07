"""Small UTF-8 PO reader and GNU MO writer supporting plural messages."""
import ast
import struct

def read_po(path):
    messages={}; entry={}; active=None
    def finish():
        if 'id' not in entry:return
        key=entry.get('context','')+'\x04' if entry.get('context') else ''
        key+=entry['id']
        if 'plural' in entry:key+='\0'+entry['plural']
        value='\0'.join(entry.get('str'+str(i),'') for i in range(2)) if 'plural' in entry else entry.get('str','')
        if key in messages:raise ValueError('Duplicate translation: '+key)
        messages[key]=value
    for line in path.read_text(encoding='utf-8').splitlines()+['']:
        if not line.strip():
            finish();entry={};active=None;continue
        if line.startswith('#'):continue
        if line.startswith('msgctxt '):active='context';part=line[8:]
        elif line.startswith('msgid_plural '):active='plural';part=line[13:]
        elif line.startswith('msgid '):
            if 'id' in entry:finish();entry={}
            active='id';part=line[6:]
        elif line.startswith('msgstr['):active='str'+line[7:line.index(']')];part=line[line.index(']')+2:]
        elif line.startswith('msgstr '):active='str';part=line[7:]
        elif line.startswith('"') and active:entry[active]+=ast.literal_eval(line);continue
        else:continue
        entry[active]=ast.literal_eval(part)
    return messages

def write_mo(messages,path):
    pairs=sorted((k.encode(),v.encode()) for k,v in messages.items());count=len(pairs)
    keys=b'';values=b'';kt=[];vt=[];offset=28+16*count
    for k,v in pairs:
        kt.append((len(k),offset+len(keys)));keys+=k+b'\0'
        vt.append((len(v),len(values)));values+=v+b'\0'
    table=b''.join(struct.pack('<II',*x) for x in kt)+b''.join(struct.pack('<II',n,offset+len(keys)+pos) for n,pos in vt)
    path.write_bytes(struct.pack('<7I',0x950412de,0,count,28,28+8*count,0,0)+table+keys+values)
