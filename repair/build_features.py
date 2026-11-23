"""Build feature changes against the installed portable distribution."""
import struct, marshal, zlib, types, json, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / 'repair/features'
BACKEND = ROOT / 'resources/backend/api.exe'
BASELINE = ROOT / 'repair/before-template-and-branding'
COOKIE = struct.Struct('!8sIIII64s')
ENTRY = struct.Struct('!IIIIBc')
CHANGED = {'video.outro', 'server.montage_api', 'server.montage_jobs', 'video_editor.montage', 'video_editor.montage_render', 'server.api','core.state','server.jobs','video_editor.audio'}

def extend_module(original, extension, filename):
    wrapper = compile('exec("__ORIGINAL_MODULE__")\n' + extension, filename, 'exec')
    return wrapper.replace(co_consts=tuple(original if v == '__ORIGINAL_MODULE__' else v for v in wrapper.co_consts))

def remove_outro(original):
    helpers = {c.co_name: c for c in original.co_consts if isinstance(c, types.CodeType) and c.co_name in ('_overwrite_in_place', '_replace_with_retry')}
    assert len(helpers) == 2
    code = compile((FEATURES/'outro.py').read_text(encoding='utf8'), 'video/outro.py', 'exec')
    return code.replace(co_consts=tuple(helpers.get(c.co_name, c) if isinstance(c, types.CodeType) else c for c in code.co_consts))

def patch_pyz(pyz):
    old = dict(marshal.loads(pyz[struct.unpack('!i',pyz[8:12])[0]:]))
    out = bytearray(pyz[:12]); new = []
    for name,(kind,offset,length) in old.items():
        payload = pyz[offset:offset+length]
        if name in CHANGED:
            code = marshal.loads(zlib.decompress(payload))
            if name == 'video.outro': code = remove_outro(code)
            else:
                extension = FEATURES/(name.rsplit('.',1)[1]+'_extension.py')
                source = extension.read_text(encoding='utf8')
                if name == 'video_editor.montage_render':
                    source += '\n' + (FEATURES/'bouncing_ball.py').read_text(encoding='utf8')
                code = extend_module(code, source, name.replace('.','/')+'.py')
            payload = zlib.compress(marshal.dumps(code))
        new.append((name,(kind,len(out),len(payload))))
        out.extend(payload)
    toc_pos = len(out)
    out.extend(marshal.dumps(new)); out[8:12] = struct.pack('!i',toc_pos)
    for name,(_,offset,length) in new:
        if name not in CHANGED:
            _,a,b = old[name]
            assert bytes(out[offset:offset+length]) == pyz[a:a+b],name
    return bytes(out)

def build_backend():
    source = BASELINE/'api.exe' if (BASELINE/'api.exe').exists() else BACKEND
    b = source.read_bytes(); i = b.rfind(b'MEI\x0c\x0b\x0a\x0b\x0e')
    magic,size,toc_off,toc_len,pyver,pylib = COOKIE.unpack_from(b,i)
    assert i+COOKIE.size == len(b) and pyver==311
    base = len(b)-size; pos = base+toc_off
    data = bytearray(); entries=[]
    while pos < base+toc_off+toc_len:
        n,o,l,u,c,t = ENTRY.unpack_from(b,pos)
        name = b[pos+18:pos+n]; payload = b[base+o:base+o+l]
        if name.rstrip(b'\0') == b'PYZ.pyz':
            assert c==0
            payload=patch_pyz(payload); u=len(payload)
        entries.append(ENTRY.pack(n,len(data),len(payload),u,c,t)+name)
        data.extend(payload); pos += n
    toc_pos=len(data); toc=b''.join(entries); data.extend(toc)
    data.extend(COOKIE.pack(magic,len(data)+COOKIE.size,toc_pos,len(toc),pyver,pylib))
    target=BACKEND.with_name('api.features.exe'); target.write_bytes(b[:base]+data)
    print('Built backend:',target)

def build_ui():
    asar = ROOT/'resources/app.asar'
    source = BASELINE/'app.asar' if (BASELINE/'app.asar').exists() else asar
    b=source.read_bytes(); header_size=struct.unpack_from('<I',b,4)[0]
    header=json.loads(b[16:16+struct.unpack_from('<I',b,12)[0]])
    files=[]
    def gather(tree,path=''):
        for name,item in tree['files'].items():
            full=path+'/'+name
            if 'files' in item: gather(item,full)
            elif 'offset' in item:
                start=8+header_size+int(item['offset'])
                files.append((full,item,b[start:start+item['size']]))
    gather(header)
    data=bytearray(); changed=[]
    for name,item,payload in files:
        if name.startswith('/out/renderer/assets/index-') and name.endswith('.js'):
            ui=payload.decode('utf8')
            start=ui.index('function BrandingCard() {'); end=ui.index('function Settings() {',start)
            ui=ui[:start]+ui[end:]
            anchor='/* @__PURE__ */ jsxRuntimeExports.jsx(BrandingCard, {})'
            assert ui.count(anchor)==1
            ui=ui.replace(anchor,'null')
            anchor='function AddVideos({ onAdded }) {'
            assert ui.count(anchor)==1
            ui=ui.replace(anchor,(FEATURES/'template_controls.js').read_text(encoding='utf8')+'\n'+anchor)
            anchor='        slot.error && /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-sm text-error mt-1", children: slot.error })'
            assert ui.count(anchor)==1
            ui=ui.replace(anchor,'        jsxRuntimeExports.jsx(VideoMontageChoice, { options: slot.options, onChange: (change) => patchOptions(slot.key, change) }),\n'+anchor)
            ui = extend_ui(ui)
            (ROOT/'repair/ui-modified.js').write_text(ui,encoding='utf8')
            payload=ui.encode('utf8'); changed.append(name)
            if 'integrity' in item:
                block_size=item['integrity']['blockSize']
                item['integrity']={'algorithm':'SHA256','hash':hashlib.sha256(payload).hexdigest(),'blockSize':block_size,'blocks':[hashlib.sha256(payload[i:i+block_size]).hexdigest() for i in range(0,len(payload),block_size)]}
        item['offset']=str(len(data)); item['size']=len(payload); data.extend(payload)
    assert len(changed)==1,changed
    encoded=json.dumps(header,ensure_ascii=False,separators=(',',':')).encode('utf8')
    padding=b'\0'*((-len(encoded))%4)
    payload_len=4+len(encoded)+len(padding)
    header_pickle=struct.pack('<II',payload_len,len(encoded))+encoded+padding
    result=struct.pack('<II',4,len(header_pickle))+header_pickle+data
    # Validate all packed files after rebuilding the header and offsets.
    new_header_size=struct.unpack_from('<I',result,4)[0]
    for name,item,old_payload in files:
        off=8+new_header_size+int(item['offset'])
        if name not in changed: assert result[off:off+item['size']]==old_payload,name
    target=asar.with_name('app.features.asar'); target.write_bytes(result)
    print('Built UI:',target)
    print('Preserved all other UI assets and backend modules')

def extend_ui(ui):
    def replace_once(old,new):
        nonlocal ui
        assert ui.count(old)==1,old[:100]
        ui=ui.replace(old,new)
    replace_once('function MontageTemplates() {', (FEATURES/'secondary_sources.js').read_text(encoding='utf8')+'\nfunction MontageTemplates() {')
    replace_once('  const split = (patch) => update({ split: { ...settings.split, ...patch } });',
                 '  const split = (patch) => setSettings((current) => ({ ...current, split: { ...current.split, ...(typeof patch === "function" ? patch(current.split) : patch) } }));')
    start = ui.index('        /* @__PURE__ */ jsxRuntimeExports.jsx(\n          Select,\n          {\n            label: "Выбор видео",')
    end = ui.index('        /* @__PURE__ */ jsxRuntimeExports.jsx(\n          Select,\n          {\n            label: "Доля основного видео",', start)
    legacy = ui[start:end]
    ui = ui[:start] + '''        jsxRuntimeExports.jsx(SecondaryVideoSources, { options: settings.split, patch: split, perform }),
        !(settings.split.files?.length || settings.split.bouncing_ball) && jsxRuntimeExports.jsxs(jsxRuntimeExports.Fragment, { children: [
''' + legacy + '''        ] }),
''' + ui[end:]
    replace_once('function App() {', (FEATURES/'queue_mini.js').read_text(encoding='utf8')+'\nfunction App() {')
    replace_once('    wizard && /* @__PURE__ */ jsxRuntimeExports.jsx(', '    jsxRuntimeExports.jsx(QueueMiniWindow, {}),\n    wizard && /* @__PURE__ */ jsxRuntimeExports.jsx(')
    replace_once('const normToken = (w2) => w2.toLowerCase().replace(/[^a-z]/g, "");',
        (FEATURES/'censor.js').read_text(encoding='utf8')+'\nconst normToken = (w2) => w2.toLowerCase().replace(/[^\\p{L}]/gu, "");')
    start=ui.index('  const censorProfanity = () => {')
    end=ui.index('  const wordMuted$1 =',start)
    ui=ui[:start]+'''  const censorProfanity = () => {
    const result=censorWordCenters(edit,words2,duration);
    if(!result.count){setNotice("Мат не найден. Если распознавание ошиблось, исправьте текст слова в редакторе.");return;}
    push(result.edit);
    setNotice(`Обработано слов: ${result.count}. Заглушается середина; начало и конец остаются слышимыми. Нажмите Apply.`);
  };
'''+ui[end:]
    start=ui.index('function toggledWord(edit, w2, duration) {')
    end=ui.index('function hookOf(',start)
    ui=ui[:start]+'''function toggledWord(edit,w2,duration) {
  const center=centerCensorRange(w2,duration),full=fullWordRange(w2,duration);
  if(!center)return edit;
  if(wordMuted(edit,w2))return {...edit,muted_words:edit.muted_words.filter(m=>!(Math.abs(m.start-w2.start)<0.03&&m.word===w2.word)),mutes:edit.mutes.filter(r=>!sameCensorRange(r,full)&&!sameCensorRange(r,center))};
  return {...edit,muted_words:[...edit.muted_words,{start:w2.start,end:w2.end,word:w2.word}],mutes:[...edit.mutes,center]};
}
'''+ui[end:]
    replace_once('title: t("Mute every swear word — audio silenced and captions censored (f**k), so platforms can\'t flag either"),','title: "Цензура русского и английского мата: приглушить середину слова, сохранив начало и конец; скрыть середину в субтитрах",')
    replace_once('" Censor swearing"','" Цензура мата: середина слова"')
    replace_once('"Click a word to mute it (audio silent, caption censored)."','"Нажмите любое слово: заглушается только середина, начало и конец остаются слышимыми. Текст скрывается звёздочками."')
    replace_once('"Un-mute this word (audio and caption come back)"','"Убрать цензуру слова: восстановить звук и текст"')
    replace_once('"Mute this word — audio goes silent and the caption shows it censored (f**k)"','"Заглушить середину слова, сохранив начало и конец; скрыть середину в субтитрах"')
    replace_once('function ClipStudio({', (FEATURES/'existing_clips.js').read_text(encoding='utf8')+'\nfunction ClipStudio({')
    replace_once('function TimelineEditor({', (FEATURES/'source_range.js').read_text(encoding='utf8')+'\nfunction TimelineEditor({')
    replace_once('function SourceRangeEditor({', (FEATURES/'original_restore.js').read_text(encoding='utf8')+'\nfunction SourceRangeEditor({')
    replace_once('''  onTranslationPreview,
  watermark,''','''  onTranslationPreview,
  onRestored,
  watermark,''')
    replace_once('''          onTranslationPreview: setTranslated,
          watermark,''','''          onTranslationPreview: setTranslated,
          onRestored: () => { onChanged(); onClose(); },
          watermark,''')
    anchor='''    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "space-y-1", children: [
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex items-center gap-1.5 text-xs", children: [
        /* @__PURE__ */ jsxRuntimeExports.jsxs("span", { className: "text-muted mr-auto", children: [
          "Timeline · Ctrl+scroll to zoom",'''
    replace_once(anchor,'''    jsxRuntimeExports.jsx(OriginalClipRestore, { clip, onRestored, disabled: busy }),
    jsxRuntimeExports.jsx(SourceRangeEditor, { clip, onChanged, disabled: busy || dirty }),
'''+anchor)
    replace_once('  const [selectedClip, setSelectedClip] = reactExports.useState(null);', '''  const [selectedClip, setSelectedClip] = reactExports.useState(null);
  const [montageClipIds, setMontageClipIds] = reactExports.useState([]);
  reactExports.useEffect(() => { setMontageClipIds([]); }, [activeVideo]);
  reactExports.useEffect(() => { setMontageClipIds((ids) => ids.filter((id) => clips2.some((clip) => clip.id === id))); }, [clips2]);''')
    replace_once('        exportNotice && /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-sm text-accent", children: exportNotice }),', '''        jsxRuntimeExports.jsx(ExistingClipTemplates, { clipIds: montageClipIds, shownIds: shownClips.map((clip) => clip.id), onSelect: setMontageClipIds, videoId: activeVideo }),
        exportNotice && /* @__PURE__ */ jsxRuntimeExports.jsx("p", { className: "text-sm text-accent", children: exportNotice }),''')
    old='''          shownClips.map((clip) => /* @__PURE__ */ jsxRuntimeExports.jsx(
            ClipCard,
            {
              clip,
              selected: clip.id === selectedClip,
              onClick: () => setSelectedClip(clip.id),
              onDelete: () => deleteClip(clip.id),
              onToggleExported: () => toggleExported(clip),
              onPublish: () => setPublishOne(clip)
            },
            clip.id
          )),'''
    new='''          shownClips.map((clip) => jsxRuntimeExports.jsxs("div", { className: "space-y-2", children: [
            jsxRuntimeExports.jsxs("label", { className: "flex items-center gap-2 text-sm cursor-pointer", children: [
              jsxRuntimeExports.jsx("input", { type: "checkbox", checked: montageClipIds.includes(clip.id), onChange: (e) => setMontageClipIds((ids) => e.target.checked ? [...new Set([...ids, clip.id])] : ids.filter((id) => id !== clip.id)), "aria-label": `Применить шаблон к клипу ${clip.id}` }),
              "Выбрать для шаблона"
            ] }),
            jsxRuntimeExports.jsx(ClipCard, { clip, selected: clip.id === selectedClip, onClick: () => setSelectedClip(clip.id), onDelete: () => deleteClip(clip.id), onToggleExported: () => toggleExported(clip), onPublish: () => setPublishOne(clip) })
          ] }, clip.id)),'''
    replace_once(old,new)
    anchor='''        library("video", settings.split.folder, (folder) => split({ folder })),'''
    replace_once(anchor,anchor+'''
        jsxRuntimeExports.jsx(Num, { label: "Скорость дополнительного видео (0,5×–4×)", value: settings.split.speed ?? 1, min: 0.5, max: 4, step: "any", onChange: (speed) => split({ speed }) }),
        jsxRuntimeExports.jsx(Check, { label: "Отзеркалить основное видео (субтитры остаются читаемыми)", value: !!settings.mirror_main, onChange: (mirror_main) => update({ mirror_main }) }),
        jsxRuntimeExports.jsx(Check, { label: "Отзеркалить дополнительное видео", value: !!settings.split.mirror, onChange: (mirror) => split({ mirror }) }),
        jsxRuntimeExports.jsx(Select, { label: "Основное видео: размер и фон", value: settings.main_framing ?? "blur", choices: [["blur", "Весь кадр на размытом фоне — без сильного приближения"], ["crop", "Заполнить блок с обрезкой по краям"]], onChange: (main_framing) => update({ main_framing }) }),
        (settings.main_framing ?? "blur") === "blur" && jsxRuntimeExports.jsx(Num, { label: "Размер основного кадра на фоне (0,5–1)", value: settings.main_scale ?? 1, min: 0.5, max: 1, step: "any", onChange: (main_scale) => update({ main_scale }) }),
        jsxRuntimeExports.jsx("p", { className: "text-xs text-muted", children: "Режим размытого фона сохраняет весь основной кадр. Для отражения без переворота субтитров Clips Kitty нужны исходный ролик и расшифровка (либо файл .ass). Текст, вшитый в стороннее видео, является частью картинки и тоже отражается." }),
        jsxRuntimeExports.jsx(Check, { label: "Заполнять весь кадр без чёрных полос (оба видео)", value: settings.split.fill_frame !== false, onChange: (fill_frame) => split({ fill_frame }) }),
        jsxRuntimeExports.jsx("p", { className: "text-xs text-muted", children: "Оба видео заполняют свои блоки на всю ширину. Пропорции сохраняются, лишнее обрезается по центру; записанные чёрные поля определяются автоматически." }),
        jsxRuntimeExports.jsx("p", { className: "text-xs text-muted", children: "Можно ввести любое значение в диапазоне, например 2.3. Основной клип и музыка сохраняют свою скорость." }),''')
    return ui

build_backend()
build_ui()
