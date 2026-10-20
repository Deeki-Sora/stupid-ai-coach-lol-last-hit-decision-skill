"""Associate model boxes with bars and apply frame-level minion constraints."""
from math import exp, log
from statistics import median


def associate_model_bars(models, bars, *, max_vertical_gap=90.0, max_horizontal_gap=70.0):
    """Return proposal rows; model and bar identities remain unconfirmed.

    Boxes use ``[x, y, width, height]`` in source-image pixels. A bar must be
    above the model, its horizontal center must be close, and the candidate
    with the smallest normalized gap wins. This prevents a nearby minion bar
    from being assigned solely by color.
    """
    rows=[]; used=set()
    for model in models:
        x,y,w,h=model['box']; mcx=x+w/2; mtop=y
        candidates=[]
        for index,bar in enumerate(bars):
            if index in used: continue
            bx,by,bw,bh=bar['box']; bcx=bx+bw/2; bbottom=by+bh
            horizontal=abs(bcx-mcx); vertical=mtop-bbottom
            if vertical < 0 or vertical > max_vertical_gap or horizontal > max_horizontal_gap: continue
            score=(horizontal/max_horizontal_gap)+(vertical/max_vertical_gap)
            candidates.append((score,index,bar))
        if not candidates:
            rows.append(dict(model_track_id=model.get('track_id'),bar_track_id=None,
                             model_box=model['box'],bar_box=None,status='unmatched_model',
                             confidence=0.0,requires_confirmation=True));continue
        score,index,bar=min(candidates,key=lambda item:item[0]);used.add(index)
        confidence=max(0.0,min(0.99,1.0-score/2.0))
        rows.append(dict(model_track_id=model.get('track_id'),bar_track_id=bar.get('track_id'),
                         model_box=model['box'],bar_box=bar['box'],
                         bar_center=[bar['box'][0]+bar['box'][2]/2,bar['box'][1]+bar['box'][3]/2],
                         status='model_bar_association_proposal',confidence=round(confidence,3),
                         requires_confirmation=True))
    return rows


def _unit_geometry(unit):
    """Return width, height and area for xywh or xyxy detector records."""
    if unit.get('bbox_xyxy') is not None:
        x1, y1, x2, y2 = map(float, unit['bbox_xyxy'])
        width, height = x2 - x1, y2 - y1
    else:
        _, _, width, height = map(float, unit['box'])
    return width, height, width * height


def _unit_class(unit):
    value = unit.get('class_name', unit.get('class', unit.get('kind', '')))
    return str(value).lower()


def _identity_index(rows, target):
    return next(index for index, row in enumerate(rows) if row is target)


def constrain_siege_candidates(units, *, minimum_area_ratio=1.30):
    """Keep at most one size-plausible siege minion per side in one frame.

    The detector may score several classes for an object, but its ordinary
    prediction output contains only the highest class. This pass operates on
    those top-class rows after visible same-side health-bar association.

    Relative geometry is computed against the median non-siege minion of the
    same side in the same frame, so camera zoom does not require a fixed pixel
    size. When fewer than two ordinary references exist, geometry is marked
    unknown and only the one-per-side rule is applied.
    """
    output = list(units)
    rejected = []
    for side in ('blue', 'red'):
        side_rows = [u for u in units if _unit_class(u).startswith(side + '_')]
        ordinary = [u for u in side_rows if not _unit_class(u).endswith('_siege')]
        siege = [u for u in side_rows if _unit_class(u).endswith('_siege')]
        if not siege:
            continue

        references_available = len(ordinary) >= 2
        if references_available:
            geometry = [_unit_geometry(u) for u in ordinary]
            mw = median(g[0] for g in geometry)
            mh = median(g[1] for g in geometry)
            ma = median(g[2] for g in geometry)

        ranked = []
        for original in siege:
            width, height, area = _unit_geometry(original)
            confidence = float(original.get('confidence', 0.0))
            if references_available and mw > 0 and mh > 0 and ma > 0:
                width_ratio, height_ratio, area_ratio = width / mw, height / mh, area / ma
                plausible = area_ratio >= minimum_area_ratio and (height_ratio >= 1.20 or area_ratio >= 1.55)
                # Training annotations cluster near 1.38x width, 1.40x height
                # and 1.85x area. A soft score ranks plausible duplicates.
                distance = ((log(max(width_ratio, .01) / 1.38) / .45) ** 2
                            + (log(max(height_ratio, .01) / 1.40) / .40) ** 2
                            + (log(max(area_ratio, .01) / 1.85) / .45) ** 2)
                size_score = exp(-0.5 * distance)
                enriched = {**original, 'siege_size_ratios': {
                    'width': round(width_ratio, 3), 'height': round(height_ratio, 3),
                    'area': round(area_ratio, 3)}, 'siege_size_score': round(size_score, 4)}
                if not plausible:
                    rejected.append({**enriched, 'reason': 'siege_relative_size_implausible'})
                    output.pop(_identity_index(output, original))
                    continue
            else:
                size_score = 0.5
                enriched = {**original, 'siege_size_ratios': None, 'siege_size_score': size_score}
            ranked.append((0.75 * confidence + 0.25 * size_score, original, enriched))

        if not ranked:
            continue
        ranked.sort(key=lambda item: item[0], reverse=True)
        _, winner_original, winner = ranked[0]
        # Replace the original winner with its diagnostic-enriched record.
        output[_identity_index(output, winner_original)] = winner
        for _, original, duplicate in ranked[1:]:
            output.pop(_identity_index(output, original))
            rejected.append({**duplicate, 'reason': 'siege_side_frame_limit'})
    return output, rejected
