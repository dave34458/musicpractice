import math


def score_result(result):
    rating = result.get('rating', 0) or 0
    votes = result.get('votes', 0) or 0
    tab_type = result.get('type', '').lower()

    if rating <= 0 and votes <= 0:
        return 0

    trust = rating * math.log2(votes + 2)

    type_bonus = 1.0 if tab_type == 'chords' else 0.7 if tab_type == 'tabs' else 0.85

    has_key = 1.05 if result.get('key') else 1.0

    return round(trust * type_bonus * has_key, 4)


def rank_results(results):
    scored = [(score_result(r), r) for r in results]
    scored.sort(key=lambda x: -x[0])
    ranked = []
    for i, (score, r) in enumerate(scored):
        r = dict(r)
        r['rank_score'] = score
        r['recommended'] = i == 0
        ranked.append(r)
    return ranked
