import re

TUNING_PATTERN = re.compile(r'^[\s(]*\d{6}|^EADGBe', re.IGNORECASE)
TAB_LINE = re.compile(r'^[eBGDAEbgdae]+\||^\|[\d\-]+\|.*\|[\d\-]+\||^\|-{3,}')
META_PATTERN = re.compile(r'^\(x\d+\)$', re.IGNORECASE)
SKIP_PATTERN = re.compile(r'^capo\s|^tuning|^standard|^\d+\.\s|^http|^www', re.IGNORECASE)
SECTION_PATTERN = re.compile(
    r'^\[?(intro|verse|chorus|bridge|outro|pre-chorus|refrain|interlude|solo|'
    r'tag|breakdown|coda|couplet|instrumental|ending|part)\s*(\d*)\]?\s*$',
    re.IGNORECASE
)

def parse_chart(raw_text):
    if not raw_text:
        return {'sections': [], 'lyrics_only': []}

    text = re.sub(r'\[tab\]', '', raw_text)
    text = re.sub(r'\[/tab\]', '', text)
    lines = text.split('\n')

    sections = []
    current_section = None
    prev_chords = ''
    in_preamble = True

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if SKIP_PATTERN.match(stripped):
            continue
        if TUNING_PATTERN.match(stripped):
            continue

        m = SECTION_PATTERN.match(stripped)
        if m:
            label = (m.group(1) + ' ' + m.group(2)).strip()
            if current_section and (current_section['chords'] or current_section['lyrics']):
                sections.append(current_section)
            current_section = {'label': label, 'chords': [], 'lyrics': []}
            in_preamble = False
            prev_chords = ''
            continue

        chords, lyrics = extract_chord_line(line)

        if re.match(r'^\(?[0-9x]{4,7}\)?$', lyrics):
            continue
        if re.match(r'^\(x\d+\)$', lyrics):
            continue
        if TAB_LINE.search(stripped):
            continue

        if in_preamble and chords:
            in_preamble = False

        if in_preamble:
            continue

        if current_section is None:
            label = 'verse' if chords else ''
            current_section = {'label': label, 'chords': [], 'lyrics': []}
            in_preamble = False

        current_section['chords'].append(chords)
        current_section['lyrics'].append(lyrics)
        prev_chords = chords

    if current_section and (current_section['chords'] or current_section['lyrics']):
        sections.append(current_section)

    if not sections:
        sections = [{'label': '', 'chords': [], 'lyrics': []}]
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if SKIP_PATTERN.match(stripped) or TUNING_PATTERN.match(stripped):
                continue
            c, l = extract_chord_line(line)
            sections[0]['chords'].append(c)
            sections[0]['lyrics'].append(l)

    lyrics_only = []
    for sec in sections:
        for l in sec['lyrics']:
            cleaned = re.sub(r'\s+', ' ', l).strip()
            if cleaned:
                lyrics_only.append(cleaned)

    return {
        'sections': sections,
        'lyrics_only': lyrics_only,
        'all_chords': extract_unique_chords(sections),
    }


def extract_chord_line(line):
    raw = line.rstrip('\r\n')
    if '[ch]' not in raw:
        return '', raw.strip()

    chars = [' '] * len(raw)
    for m in re.finditer(r'\[ch\](.*?)\[/ch\]', raw):
        chord = m.group(1)
        start = m.start()
        for j, c in enumerate(chord):
            if start + j < len(chars):
                chars[start + j] = c
    chord_line = ''.join(chars).rstrip()

    lyric_text = re.sub(r'\[ch\].*?\[/ch\]', '', raw).rstrip()
    if lyric_text.strip():
        return chord_line, lyric_text

    return chord_line, ''


def snap_chords_to_words(chord_line, lyric_line):
    if not chord_line.strip() or not lyric_line.strip():
        return chord_line

    chords = [(m.group(), m.start()) for m in re.finditer(r'\S+', chord_line)]
    words = [(m.group(), m.start()) for m in re.finditer(r'\S+', lyric_line)]

    if not chords or not words:
        return chord_line

    # For multi-chord lines, strip leading whitespace from all chords
    # except the first, which keeps its original position. Single-chord
    # lines use leading whitespace to position over a specific word.
    if len(chords) > 1:
        lead = len(chord_line) - len(chord_line.lstrip())
        chords = [(chords[0][0], chords[0][1])] + [(name, max(0, pos - lead)) for name, pos in chords[1:]]

    new_chord = [' '] * (len(lyric_line) + max(len(c[0]) for c in chords))
    for chord, cpos in chords:
        wpos = min(words, key=lambda w: abs(cpos - w[1]))[1]
        for j, c in enumerate(chord):
            if wpos + j < len(new_chord):
                new_chord[wpos + j] = c
    return ''.join(new_chord).rstrip()


def simplify_chord(name):
    name = name.split('/')[0]
    m = re.match(r'^([A-G][#b]?)(m(?!a|j))?', name)
    if not m:
        m = re.match(r'^([A-G][#b]?)', name)
    if not m:
        return name
    root = m.group(1)
    quality = m.group(2) or ''
    rest = name[m.end():]

    sus = re.search(r'(sus\d*)', rest)
    if sus:
        return root + quality + sus.group(1)

    qual = re.match(r'(dim|aug|[+\u00b0\u00a2])\d*', rest)
    if qual:
        return root + ''.join(c for c in qual.group(1) if not c.isdigit())

    if not quality:
        sev = re.match(r'(7)', rest)
        if sev:
            return root + '7'

    return root + quality


def simplify_chord_line(chord_line):
    return re.sub(r'\S+', lambda m: simplify_chord(m.group()), chord_line)


def extract_unique_chords(sections):
    chords = set()
    for sec in sections:
        for line in sec['chords']:
            for c in line.split():
                c = c.strip()
                if c:
                    chords.add(c)
    return chords
