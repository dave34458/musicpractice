from collections import defaultdict
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .services.ug_scraper import search_songs, fetch_chart
from .services.chart_parser import parse_chart, snap_chords_to_words, simplify_chord_line
from .services.chart_ranker import score_result


@login_required
def search(request):
    query = request.GET.get('q', '')
    groups = []
    if query:
        results = search_songs(query)
        results = [r for r in results if r.get('type', '').lower() == 'chords']
        scored = [(score_result(r), r) for r in results]
        scored.sort(key=lambda x: -x[0])

        by_artist = defaultdict(list)
        for score, r in scored:
            r['rank_score'] = score
            by_artist[r['artist'] or 'Unknown'].append(r)

        for artist in by_artist:
            artist_results = by_artist[artist]
            artist_results.sort(key=lambda x: (-x['rank_score'], x['title'].lower()))
            total_votes = sum(r.get('votes', 0) or 0 for r in artist_results)

            seen = set()
            for r in artist_results:
                key = (r['title'].lower(), r['artist'].lower())
                r['recommended'] = key not in seen
                seen.add(key)

            groups.append({
                'artist': artist,
                'results': artist_results,
                'total_votes': total_votes,
            })

        groups.sort(key=lambda g: -g['total_votes'])

    return render(request, 'chordfinder/search.html', {
        'query': query,
        'groups': groups,
    })


@login_required
def chart_view(request):
    url = request.GET.get('url', '')
    if not url:
        return redirect('chordfinder:search')

    raw = fetch_chart(url)
    if not raw:
        return render(request, 'chordfinder/search.html', {
            'error': 'Could not fetch chord chart from Ultimate Guitar.',
            'query': '',
            'groups': [],
        })

    chart = parse_chart(raw['raw_chart'])
    chart['title'] = raw['title']
    chart['artist'] = raw['artist']
    chart['source_url'] = raw['source_url']
    chart['all_chords'] = list(chart['all_chords'])
    for sec in chart['sections']:
        rows = []
        used = set()
        for i in range(len(sec['chords'])):
            if i in used:
                continue
            chord = sec['chords'][i]
            lyric = sec['lyrics'][i]
            if chord.strip() and lyric.strip():
                snapped = snap_chords_to_words(chord, lyric.strip())
                rows.append({'chords': snapped, 'lyric': lyric.strip(), 'simplified': simplify_chord_line(snapped)})
                used.add(i)
            elif chord.strip() and not lyric.strip():
                next_lyric = sec['lyrics'][i+1].rstrip() if i+1 < len(sec['lyrics']) else ''
                snapped = snap_chords_to_words(chord, next_lyric.strip())
                rows.append({'chords': snapped, 'lyric': next_lyric.strip(), 'simplified': simplify_chord_line(snapped)})
                used.add(i)
                if i+1 < len(sec['lyrics']):
                    used.add(i+1)
        sec['pairs'] = rows

    return render(request, 'chordfinder/chart.html', {
        'chart': chart,
    })
