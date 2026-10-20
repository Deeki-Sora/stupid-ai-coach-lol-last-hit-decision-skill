"""Risk-aware short-window decision and two-layer evaluation formulas."""
import math
from .layered_evaluation import final_layer_score


DEFAULT_METRIC_WEIGHTS={
    "gold_gain":1.0,"xp_gain":0.02,"hp_damage":-0.5,"hp_deficit_change":-0.5,
    "mana_spent":-0.15,"cooldown_remaining_s":-0.1,"pending_enemy_gold":-0.25,
    "pending_enemy_xp":-0.01}


def _finite(value,label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError(label+" must be finite")
    return float(value)


def weighted_utility(metrics,weights=None,scales=None):
    weights=weights or DEFAULT_METRIC_WEIGHTS;scales=scales or {}
    result=0.;terms={}
    for key,weight in weights.items():
        if key not in metrics or metrics[key] is None:continue
        scale=_finite(scales.get(key,1.),"metric scale")
        if scale<=0:raise ValueError("metric scales must be positive")
        term=_finite(metrics[key],key)*_finite(weight,key+" weight")/scale
        terms[key]=term;result+=term
    return dict(value=result,terms=terms,missing=sorted(set(weights)-set(terms)))


def lower_cvar(values,probabilities=None,alpha=.2):
    """Expected value in the worst lower-alpha tail of utility values."""
    if not 0<alpha<=1:raise ValueError("alpha must be in (0,1]")
    vals=[_finite(x,"utility") for x in values]
    if not vals:return None
    if probabilities is None:probabilities=[1/len(vals)]*len(vals)
    if len(probabilities)!=len(vals):raise ValueError("probabilities length mismatch")
    total=sum(_finite(p,"probability") for p in probabilities)
    if total<=0:raise ValueError("probabilities must have positive mass")
    pairs=sorted(zip(vals,[p/total for p in probabilities]))
    remain=alpha;out=0.
    for value,p in pairs:
        take=min(remain,p);out+=value*take;remain-=take
        if remain<=1e-12:break
    return out/alpha


def value_of_information(action_values, observation_action_values, observation_probabilities=None):
    """VOI = expected posterior best action minus current best action."""
    if not action_values or not observation_action_values:return 0.
    prior=max(_finite(v,"action value") for v in action_values.values())
    rows=list(observation_action_values)
    if observation_probabilities is None:observation_probabilities=[1/len(rows)]*len(rows)
    if len(rows)!=len(observation_probabilities):raise ValueError("observation probability mismatch")
    total=sum(_finite(p,"observation probability") for p in observation_probabilities)
    if total<=0:raise ValueError("observation probabilities must have positive mass")
    posterior=sum((p/total)*max(_finite(v,"posterior action value") for v in row.values())
                  for p,row in zip(observation_probabilities,rows))
    return max(0.,posterior-prior)


def decision_value(outcomes,weights=None,scales=None,alpha=.2,lambda_risk=.25,voi=0.,nu_voi=.1,execute_cost=0.,kappa=.05,
                   eligible=True, eligibility_reasons=None):
    """Evaluate a finite action distribution before seeing its outcome."""
    if not outcomes:raise ValueError("at least one outcome is required")
    if eligible not in (True,False):raise ValueError("eligible must be True or False")
    if not eligible:
        return dict(eligible=False,expected_utility=None,lower_cvar=None,risk_penalty=None,
                    voi=voi,execution_cost=execute_cost,decision_value=None,utilities=[],
                    eligibility_reasons=list(eligibility_reasons or []))
    probabilities=[_finite(x.get("probability",1.),"outcome probability") for x in outcomes]
    total=sum(probabilities)
    if total<=0:raise ValueError("outcome probabilities must have positive mass")
    utilities=[weighted_utility(x.get("metrics",{}),weights,scales)["value"] for x in outcomes]
    expected=sum(p/total*u for p,u in zip(probabilities,utilities));tail=lower_cvar(utilities,probabilities,alpha)
    risk=max(0.,expected-tail);value=expected-lambda_risk*risk+nu_voi*voi-kappa*_finite(execute_cost,"execute_cost")
    return dict(eligible=True,expected_utility=expected,lower_cvar=tail,risk_penalty=risk,voi=voi,
        execution_cost=execute_cost,decision_value=value,utilities=utilities)



def _bounded(value, low=-1., high=1.):
    return max(low, min(high, float(value)))


def _projected_stock_cost(start, end, maximum, horizon_s=0., regen_per_s=0., recovery=0.):
    """Normalized stock expenditure after natural and observed recovery.

    Positive values mean depletion relative to the window start; negative values
    mean the stock ended above its start after recovery.  HP, mana, energy and
    other meters use the same side-specific normalization, so unlike raw values
    they remain comparable across champions and resource systems.
    """
    if any(value is None for value in (start, end, maximum)):
        return None
    start, end, maximum = (_finite(value, 'stock') for value in (start, end, maximum))
    if maximum <= 0:
        raise ValueError('stock maximum must be positive')
    horizon_s = _finite(horizon_s, 'horizon_s')
    regen_per_s = _finite(regen_per_s, 'regen_per_s')
    recovery = _finite(recovery, 'recovery')
    projected = min(maximum, end + max(0., horizon_s) * max(0., regen_per_s) + max(0., recovery))
    return _bounded((start - projected) / maximum)


def _relative_side_cost(a, b, field, horizon_s):
    a_cost = _projected_stock_cost(horizon_s=horizon_s, **a.get(field, {})) if isinstance(a.get(field), dict) else None
    b_cost = _projected_stock_cost(horizon_s=horizon_s, **b.get(field, {})) if isinstance(b.get(field), dict) else None
    return (b_cost - a_cost) if a_cost is not None and b_cost is not None else None



def summoner_spell_share(spells_a, spells_b):
    """Allocate a shared 100-point summoner-spell state component.

    Ready slots count as one.  If one side has a used slot and the other has a
    ready slot, the used slot contributes zero.  When both corresponding used
    spells expose remaining cooldown, their recovery values are compared by
    inverse remaining time: 40s versus 60s gives 60:40.  Unknown cooldowns are
    excluded rather than silently treated as ready.
    """
    def norm(data):
        if not isinstance(data,dict): return []
        rows=[]
        for ident,spell in data.items():
            if not isinstance(spell,dict): continue
            available=spell.get('available')
            remaining=spell.get('remaining_cooldown_s')
            if available is True: value=1.;status='ready'
            elif available is False and isinstance(remaining,(int,float)) and remaining>0:
                value=1./float(remaining);status='cooldown'
            elif available is False: value=0.;status='used_unknown'
            else: continue
            rows.append(dict(id=str(ident),value=value,status=status,remaining=remaining))
        return rows
    a,b=norm(spells_a),norm(spells_b)
    if not a and not b:return {'share_a':None,'share_b':None,'known_slots':0,'rows':[]}
    total_a=sum(x['value'] for x in a);total_b=sum(x['value'] for x in b);total=total_a+total_b
    return {'share_a':100.*total_a/total if total else None,
            'share_b':100.*total_b/total if total else None,
            'known_slots':len(a)+len(b),'rows':a+b}


def derive_cooldown_state(*, event_time_s, last_cast_time_s, cooldown_s,
                          ability_haste=0., cooldown_multiplier=1.,
                          charges_remaining=None):
    """Derive readiness from a time-stamped cast and generic cooldown inputs.

    This deliberately has no champion-specific branch.  The caller supplies
    the version-pinned base cooldown and any effective haste/multiplier already
    obtained from level, rune and item data.  The returned provenance lets a
    report distinguish a derived value from a visual observation.
    """
    values=(event_time_s,last_cast_time_s,cooldown_s,ability_haste,cooldown_multiplier)
    if any(isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value)
           for value in values):
        raise ValueError('cooldown inputs must be finite numbers')
    if cooldown_s<0 or ability_haste<0 or cooldown_multiplier<=0:
        raise ValueError('invalid cooldown inputs')
    if event_time_s<last_cast_time_s:
        raise ValueError('event time cannot precede cast time')
    effective=float(cooldown_s)*float(cooldown_multiplier)*100./(100.+float(ability_haste))
    elapsed=float(event_time_s)-float(last_cast_time_s)
    remaining=max(0.,effective-elapsed)
    if charges_remaining is not None:
        if isinstance(charges_remaining,bool) or not isinstance(charges_remaining,(int,float)) or charges_remaining<0:
            raise ValueError('charges_remaining must be nonnegative')
        available=charges_remaining>0
    else:
        available=remaining<=1e-9
    return {'available':available,'remaining_cooldown_s':remaining,
            'effective_cooldown_s':effective,'provenance':'derived_from_event_and_version_data'}


def state_utility_share(state_a, state_b, label='state', exponent=1.):
    """Allocate a state component from effective usable reserve, not raw HP.

    Each state is ``current``/``maximum`` with optional ``floor``,
    ``recoverable`` (within the declared horizon), and ``weight``.  The
    normalized usable reserve is
    ``u = weight * clip((current-floor+recoverable)/(maximum-floor),0,1)^exponent``.
    A numeric input is retained as the already-normalized linear special case.
    """
    def utility(value, side):
        if isinstance(value,(int,float)) and not isinstance(value,bool):
            if value<0: raise ValueError(label+' '+side+' must be nonnegative')
            return float(value)
        if not isinstance(value,dict): raise ValueError(label+' '+side+' must be numeric or a state object')
        current=value.get('current');maximum=value.get('maximum')
        floor=value.get('floor',0.);recoverable=value.get('recoverable',0.);weight=value.get('weight',1.)
        nums=(current,maximum,floor,recoverable,weight)
        if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in nums):
            raise ValueError(label+' state fields must be finite numbers')
        if maximum<=floor or floor<0 or recoverable<0 or weight<0 or exponent<=0:
            raise ValueError(label+' state bounds are invalid')
        reserve=max(0.,min(maximum-floor,current-floor+recoverable))/(maximum-floor)
        return float(weight)*reserve**float(exponent)
    a,b=utility(state_a,'A'),utility(state_b,'B')
    if a+b<=0: raise ValueError(label+' effective reserves must have positive total')
    return 100.*a/(a+b)



def _resolve_numeric_distance(game_value, pixel_value, pixels_per_game_unit, label):
    for value in (game_value, pixel_value):
        if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0):
            raise ValueError(label+' distance values must be nonnegative finite numbers')
    if game_value is not None:
        return float(game_value), 'game_units'
    if pixel_value is not None:
        if pixels_per_game_unit is None or isinstance(pixels_per_game_unit,bool) or not isinstance(pixels_per_game_unit,(int,float)) or not math.isfinite(pixels_per_game_unit) or pixels_per_game_unit<=0:
            return float(pixel_value), 'pixels'
        return float(pixel_value)/float(pixels_per_game_unit), 'game_units_from_pixels'
    return None, None


def effective_action_range(base_range, available, action_committed=None,
                           action_interruptible=False, controlled=False):
    """Return the range that can actually threaten during this action slice.

    A ready skill or attack has its declared range. A known unavailable action,
    a controlled unit, or a known committed non-interruptible action, has
    effective range zero.
    ``None`` remains unknown so the caller cannot silently turn missing timing
    evidence into a safe position.
    """
    if base_range is None:
        return None
    if isinstance(base_range,bool) or not isinstance(base_range,(int,float)) or not math.isfinite(base_range) or base_range<0:
        raise ValueError('base_range must be a nonnegative finite number')
    if available not in (True,False,None) or action_committed not in (True,False,None) or controlled not in (True,False):
        raise ValueError('availability and action/control flags are invalid')
    if available is False:
        return 0.
    if controlled:
        return 0.
    if action_committed is True and not action_interruptible:
        return 0.
    return float(base_range) if available is True or action_committed is False else None


def distance_window_score(*, own_minion_attack=None, opponent_minion_attack=None,
                          own_damage_ready=None, opponent_damage_ready=None,
                          opponent_in_own_spell_range=None, own_in_opponent_spell_range=None,
                          opponent_spell_hit_own=None, own_spell_hit_opponent=None,
                          own_in_opponent_aa_range=None, opponent_is_farming=None,
                          own_action_committed=None, opponent_action_committed=None,
                          own_action_interruptible=False, opponent_action_interruptible=False,
                          own_controlled=False, opponent_controlled=False,
                          own_aa_ready=None, opponent_aa_ready=None,
                          distance_game_units=None, opponent_spell_range_game_units=None,
                          own_spell_range_game_units=None, distance_px=None,
                          opponent_spell_range_px=None, own_spell_range_px=None,
                          opponent_aa_range_game_units=None, own_aa_range_game_units=None,
                          opponent_aa_range_px=None, own_aa_range_px=None,
                          pixels_per_game_unit=None, edge_tolerance_game_units=100.,
                          edge_tolerance_px=None, layer_weights=(.3,.2,.3,.2)):
    """Evaluate auto-attack, spell and range-edge layers for one event window.

    The new four-layer form is auto-attack legality, auto-attack edge quality,
    spell readiness/hit exposure, and spell-edge quality. A three-value weight
    tuple is accepted as a legacy form with no separate auto-attack edge layer.
    The final score is a weighted mean over known layers; unknown layers are
    removed from the denominator and reported in ``missing``.  Numeric ranges
    are optional because callers may already provide verified boolean relations.
    """
    if len(layer_weights) not in (3,4) or any(isinstance(x,bool) or not isinstance(x,(int,float)) or x<0 for x in layer_weights) or sum(layer_weights)<=0:
        raise ValueError('layer_weights must contain three (legacy) or four nonnegative values with positive total')
    if edge_tolerance_game_units is not None and (isinstance(edge_tolerance_game_units,bool) or not isinstance(edge_tolerance_game_units,(int,float)) or edge_tolerance_game_units<=0):
        raise ValueError('edge_tolerance_game_units must be positive')
    if edge_tolerance_px is not None and (isinstance(edge_tolerance_px,bool) or not isinstance(edge_tolerance_px,(int,float)) or edge_tolerance_px<=0):
        raise ValueError('edge_tolerance_px must be positive')
    flags={'own_minion_attack':own_minion_attack,'opponent_minion_attack':opponent_minion_attack,
           'own_damage_ready':own_damage_ready,'opponent_damage_ready':opponent_damage_ready,
           'opponent_in_own_spell_range':opponent_in_own_spell_range,
           'own_in_opponent_spell_range':own_in_opponent_spell_range,
           'own_in_opponent_aa_range':own_in_opponent_aa_range,'opponent_is_farming':opponent_is_farming,
           'own_action_committed':own_action_committed,'opponent_action_committed':opponent_action_committed,
           'own_aa_ready':own_aa_ready,'opponent_aa_ready':opponent_aa_ready}
    for name,value in flags.items():
        if value not in (True,False,None): raise ValueError(name+' must be True, False or None')
    if own_action_interruptible not in (True,False) or opponent_action_interruptible not in (True,False):
        raise ValueError('action_interruptible flags must be True or False')
    if own_controlled not in (True,False) or opponent_controlled not in (True,False):
        raise ValueError('controlled flags must be True or False')
    if opponent_spell_hit_own not in (True,False,None) or own_spell_hit_opponent not in (True,False,None):
        raise ValueError('spell hit outcomes must be True, False or None')
    if opponent_is_farming is None and opponent_minion_attack is not None:
        opponent_is_farming=opponent_minion_attack
    distance,unit=_resolve_numeric_distance(distance_game_units,distance_px,pixels_per_game_unit,'actor-opponent')
    own_range,own_unit=_resolve_numeric_distance(own_spell_range_game_units,own_spell_range_px,pixels_per_game_unit,'own-spell')
    opp_range,opp_unit=_resolve_numeric_distance(opponent_spell_range_game_units,opponent_spell_range_px,pixels_per_game_unit,'opponent-spell')
    own_aa_range,_=_resolve_numeric_distance(own_aa_range_game_units,own_aa_range_px,pixels_per_game_unit,'own-auto-attack')
    opp_aa_range,_=_resolve_numeric_distance(opponent_aa_range_game_units,opponent_aa_range_px,pixels_per_game_unit,'opponent-auto-attack')
    own_effective_range=effective_action_range(own_range,own_damage_ready,own_action_committed,own_action_interruptible,own_controlled)
    opp_effective_range=effective_action_range(opp_range,opponent_damage_ready,opponent_action_committed,opponent_action_interruptible,opponent_controlled)
    own_effective_aa_range=effective_action_range(own_aa_range,own_aa_ready,own_action_committed,own_action_interruptible,own_controlled)
    opp_effective_aa_range=effective_action_range(opp_aa_range,opponent_aa_ready,opponent_action_committed,opponent_action_interruptible,opponent_controlled)
    # A known unavailable or committed action cannot threaten in this slice.
    if own_damage_ready is False or own_controlled or own_action_committed is True and not own_action_interruptible:
        opponent_in_own_spell_range=False
    if opponent_damage_ready is False or opponent_controlled or opponent_action_committed is True and not opponent_action_interruptible:
        own_in_opponent_spell_range=False
    if opponent_aa_ready is False or opponent_controlled or opponent_action_committed is True and not opponent_action_interruptible:
        own_in_opponent_aa_range=False
    range_conflicts=[]
    if distance is not None and own_effective_range is not None:
        derived=distance<=own_effective_range
        if opponent_in_own_spell_range is not None and opponent_in_own_spell_range!=derived: range_conflicts.append('opponent_in_own_spell_range')
        if opponent_in_own_spell_range is None: opponent_in_own_spell_range=derived
    if distance is not None and opp_effective_range is not None:
        derived=distance<=opp_effective_range
        if own_in_opponent_spell_range is not None and own_in_opponent_spell_range!=derived: range_conflicts.append('own_in_opponent_spell_range')
        if own_in_opponent_spell_range is None: own_in_opponent_spell_range=derived
    if distance is not None and opp_effective_aa_range is not None:
        derived=distance<=opp_effective_aa_range
        if own_in_opponent_aa_range is not None and own_in_opponent_aa_range!=derived: range_conflicts.append('own_in_opponent_aa_range')
        if own_in_opponent_aa_range is None: own_in_opponent_aa_range=derived
    flags.update(opponent_in_own_spell_range=opponent_in_own_spell_range,
                 own_in_opponent_spell_range=own_in_opponent_spell_range,
                 opponent_is_farming=opponent_is_farming)
    missing=[name for name,value in flags.items() if value is None]
    points=[];reasons=[]
    # Layer 1: auto-attack legality. Not entering the range is neutral evidence.
    aa_layer=None
    if own_in_opponent_aa_range is not None:
        aa_layer=0.
        if own_in_opponent_aa_range:
            if opponent_is_farming is True:
                aa_layer=1.;reasons.append('opponent_farming_allows_auto_attack_entry')
            elif opponent_is_farming is False:
                aa_layer=-1.;reasons.append('opponent_not_farming_auto_attack_entry_illegal')
            else:
                aa_layer=None
    # Layer 2: spell readiness, target exposure and observed hit/counterplay.
    spell_layer=None
    if opponent_damage_ready is False:
        spell_layer=0.
        if own_damage_ready is True and opponent_in_own_spell_range is True:
            spell_layer+=.6;reasons.append('opponent_damage_cooldown_and_target_in_own_spell_range')
            if own_spell_hit_opponent is True: spell_layer+=.4;reasons.append('own_ready_spell_hit_opponent')
        elif own_damage_ready is True and own_in_opponent_spell_range is True:
            spell_layer+=.25;reasons.append('close_distance_allowed_while_opponent_damage_unavailable')
    elif opponent_damage_ready is True:
        spell_layer=0.
        if own_minion_attack is True:
            if own_in_opponent_spell_range is False:
                spell_layer=1.;reasons.append('last_hit_outside_ready_opponent_spell_range')
            elif own_in_opponent_spell_range is True:
                if opponent_spell_hit_own is False:
                    spell_layer=1.;reasons.append('minion_attack_exposed_but_opponent_spell_missed')
                elif opponent_spell_hit_own is True:
                    spell_layer=-1.;reasons.append('minion_attack_exposed_and_opponent_spell_hit')
                else:
                    reasons.append('minion_attack_exposure_hit_unknown')
            else:
                spell_layer=None
        elif own_minion_attack is False:
            if own_damage_ready is True and opponent_in_own_spell_range is True:
                spell_layer+=.5;reasons.append('free_window_own_damage_ready_and_opponent_in_own_range')
                if own_spell_hit_opponent is True:
                    spell_layer+=.5;reasons.append('own_ready_spell_hit_opponent')
            if own_in_opponent_spell_range is True:
                spell_layer-=.5
                if opponent_spell_hit_own is True:
                    spell_layer-=.5;reasons.append('free_window_exposed_and_opponent_spell_hit')
                else:
                    reasons.append('free_window_exposed_to_ready_opponent_spell')
        else:
            spell_layer=None
    # Layer 3: distance from the relevant verified range edge. At the edge the
    # quality is 1; at least one tolerance beyond/inside it the quality is 0.
    edge_terms=[]
    margins=[]
    if distance is not None and opp_effective_range is not None and opp_effective_range>0:
        margins.append((distance-opp_effective_range, 'opponent_spell_edge', edge_tolerance_game_units if unit.startswith('game') else edge_tolerance_px))
    if distance is not None and own_effective_range is not None and own_effective_range>0:
        margins.append((distance-own_effective_range, 'own_spell_edge', edge_tolerance_game_units if own_unit.startswith('game') else edge_tolerance_px))
    for margin,label,tolerance in margins:
        if tolerance is None: continue
        edge_terms.append(2.*(1.-min(1.,abs(margin)/float(tolerance)))-1.)
    edge_layer=sum(edge_terms)/len(edge_terms) if edge_terms else None
    if edge_layer is not None:
        reasons.append('range_edge_quality:'+format(edge_layer,'.3g'))
    # Auto-attack edge is a second AA layer, used only for the legal baseline
    # outside the opponent's effective AA range. Entering that range is scored
    # by AA legality and endpoint payoff, not by an edge bonus.
    aa_edge_layer=None
    if distance is not None and opp_effective_aa_range is not None and opp_effective_aa_range>0 and own_in_opponent_aa_range is False:
        tolerance=edge_tolerance_game_units if unit.startswith('game') else edge_tolerance_px
        if tolerance is not None:
            margin=distance-opp_effective_aa_range
            if margin>=0:
                aa_edge_layer=2.*(1.-min(1.,margin/float(tolerance)))-1.
                reasons.append('auto_attack_edge_quality:'+format(aa_edge_layer,'.3g'))
    layers={'auto_attack':aa_layer,'auto_attack_edge':aa_edge_layer,
            'spell':None if spell_layer is None else _bounded(spell_layer),
            'spell_edge':edge_layer}
    if len(layer_weights)==3:
        weights=dict(zip(('auto_attack','spell','spell_edge'),layer_weights));weights['auto_attack_edge']=0.
    else:
        weights=dict(zip(('auto_attack','auto_attack_edge','spell','spell_edge'),layer_weights))
    known=[k for k,v in layers.items() if v is not None and weights[k]>0]
    denominator=sum(weights[k] for k in known)
    raw=sum(weights[k]*layers[k] for k in known)/denominator if denominator else 0.
    missing+=(['spell_hit'] if opponent_damage_ready is True and own_minion_attack is True and own_in_opponent_spell_range is True and opponent_spell_hit_own is None else [])
    if range_conflicts: missing+=['range_conflict:'+x for x in range_conflicts]
    effective={'own_spell_range':own_effective_range,'opponent_spell_range':opp_effective_range,
               'own_aa_range':own_effective_aa_range,'opponent_aa_range':opp_effective_aa_range}
    return {'score':50.+50.*_bounded(raw), 'raw':_bounded(raw), 'layers':layers,
            'reasons':reasons,'missing':missing,'range_conflicts':range_conflicts,
            'distance_unit':unit,'effective_ranges':effective,
            'evidence_count':len(known),'confidence':denominator/sum(layer_weights)}

def improvement_recommendations(observed, benchmark):
    """Turn measurable replay gaps into player-facing improvement items."""
    observed=observed or {};benchmark=benchmark or {};items=[]
    def gap(key,label,unit=''):
        a,b=observed.get(key),benchmark.get(key)
        if isinstance(a,(int,float)) and isinstance(b,(int,float)) and a>b:
            items.append({'type':key,'loss':a-b,'unit':unit,
                          'message':f'{label} exceeded the benchmark by {a-b:.3g}{unit}; reduce this gap before the next eligible window.'})
    gap('distance_px','Distance',' px');gap('movement_px','Movement',' px');gap('phase_delay_s','Attack-phase delay',' s')
    if isinstance(observed.get('cs'),(int,float)) and isinstance(benchmark.get('cs_upper'),(int,float)):
        loss=max(0.,benchmark['cs_upper']-observed['cs']);
        if loss:items.append({'type':'cs','loss':loss,'unit':'last hits','message':f'{loss:.3g} theoretical last-hit opportunities were not converted.'})
    if isinstance(observed.get('pressure'),(int,float)) and isinstance(benchmark.get('pressure_upper'),(int,float)):
        loss=max(0.,benchmark['pressure_upper']-observed['pressure']);
        if loss:items.append({'type':'pressure','loss':loss,'unit':'opportunity units','message':f'{loss:.3g} pressure opportunity units were left unused during free time.'})
    return items

def relative_state_utility(side_a, side_b, horizon_s, references=None, weights=None):
    """Compare two sides' receipts and recoverable state costs.

    The result is centered at zero: equal gold/XP and equal projected states
    yield zero advantage rather than a high absolute score.  ``side_a`` and
    ``side_b`` may contain ``gold_gain``, ``xp_gain``, ``hp``, ``resource``,
    ``cooldowns``, ``summoner_spells`` and ``consumables``.  Stock objects use
    ``start``, ``end``, ``maximum`` and optional ``regen_per_s``/``recovery``.
    Missing fields remain missing and are excluded from the denominator.
    """
    horizon_s = _finite(horizon_s, 'horizon_s')
    references = references or {'gold': 100., 'xp': 100., 'cooldown': 1., 'charges': 1.}
    weights = weights or {'gold': 1., 'xp': 1., 'hp_cost': 1., 'resource_cost': 1.,
                          'cooldown_cost': .5, 'summoner_cost': .75, 'consumable_cost': .5}
    terms = {}
    def receipt(key, ref):
        av, bv = side_a.get(key), side_b.get(key)
        if av is None or bv is None or ref <= 0:return
        terms[key] = _bounded((float(av)-float(bv))/float(ref)) * weights['gold' if key=='gold_gain' else 'xp']
    receipt('gold_gain', references['gold']);receipt('xp_gain', references['xp'])
    for field, key in [('hp', 'hp_cost'), ('resource', 'resource_cost')]:
        value = _relative_side_cost(side_a, side_b, field, horizon_s)
        if value is not None:terms[key] = value * weights[key]
    # Cooldowns: compare unavailable fractions at the common endpoint.
    ac, bc = side_a.get('cooldowns'), side_b.get('cooldowns')
    if isinstance(ac, dict) and isinstance(bc, dict):
        vals=[]
        for ident in set(ac) | set(bc):
            x,y=ac.get(ident),bc.get(ident)
            if isinstance(x,dict) and isinstance(y,dict) and x.get('maximum_s',0)>0 and y.get('maximum_s',0)>0:
                vals.append(_bounded(float(y.get('remaining_s',0))/float(y['maximum_s'])-
                                     float(x.get('remaining_s',0))/float(x['maximum_s'])))
        if vals:terms['cooldown_cost']=sum(vals)/len(vals)*weights['cooldown_cost']
    spell_share=summoner_spell_share(side_a.get('summoner_spells'),side_b.get('summoner_spells'))
    if spell_share['share_a'] is not None:
        terms['summoner_cost']=_bounded((spell_share['share_a']-50.)/50.)*weights['summoner_cost']
    # Consumable expenditure is a separate inventory state component.
    for field,key in [('consumables','consumable_cost')]:
        av,bv=side_a.get(field),side_b.get(field)
        if isinstance(av,dict) and isinstance(bv,dict):
            vals=[]
            for ident in set(av)|set(bv):
                x,y=av.get(ident),bv.get(ident)
                if isinstance(x,dict) and isinstance(y,dict) and x.get('available') is not None and y.get('available') is not None:
                    vals.append(float(bool(x['available']))-float(bool(y['available'])))
                elif isinstance(x,(int,float)) and isinstance(y,(int,float)):
                    vals.append(_bounded(float(x)-float(y)))
            if vals:terms[key]=sum(vals)/len(vals)*weights[key]
    receipt_keys={'gold_gain','xp_gain'}
    receipt_total=sum(terms.get(k,0.) for k in receipt_keys)
    receipt_denom=sum(abs(weights.get('gold' if k=='gold_gain' else 'xp',0.)) for k in receipt_keys if k in terms) or 1.
    cost_total=sum(v for k,v in terms.items() if k not in receipt_keys)
    cost_denom=sum(abs(weights.get(k,0.)) for k in terms if k not in receipt_keys) or 1.
    receipt_advantage=_bounded(receipt_total/receipt_denom)
    cost_advantage=_bounded(cost_total/cost_denom)
    # Receipts are the primary signal; state cost is a bounded secondary adjustment.
    combined=_bounded(receipt_advantage + .5*cost_advantage)
    return {'advantage_a':combined, 'receipt_advantage':receipt_advantage,
            'cost_advantage':cost_advantage, 'terms':terms, 'missing':
            [k for k in ('gold_gain','xp_gain','hp_cost','resource_cost','cooldown_cost','summoner_cost','consumable_cost') if k not in terms],
            'centered_score':50.+50.*combined}


def _score_ratio(actual, theoretical, label):
    actual=_finite(actual,label); theoretical=_finite(theoretical,label+' theoretical upper bound')
    if actual<0 or theoretical<=0: raise ValueError(label+' values must be nonnegative and the upper bound positive')
    return 100.*_bounded(actual/theoretical,0.,1.)


def _optional_score_ratio(actual, theoretical, label):
    # An unobserved component is missing evidence, not a numerical zero.
    if actual is None or theoretical is None:
        return None
    return _score_ratio(actual, theoretical, label)


def relative_share(value_a, value_b, label='state'):
    """Allocate a shared 100-point state component by normalized remaining value."""
    value_a=_finite(value_a,label+' A');value_b=_finite(value_b,label+' B')
    if value_a<0 or value_b<0 or value_a+value_b<=0: raise ValueError(label+' values must be nonnegative with positive total')
    return 100.*value_a/(value_a+value_b)


def matchup_adjusted_score(observed_share_a, prior_share_a):
    """Reward outperforming a declared matchup prior without treating it as skill."""
    observed_share_a=_finite(observed_share_a,'observed matchup share')
    prior_share_a=_finite(prior_share_a,'prior matchup share')
    if not 0<=observed_share_a<=100 or not 0<=prior_share_a<=1:
        raise ValueError('matchup shares must be observed 0..100 and prior 0..1')
    return _bounded(50.+observed_share_a-prior_share_a*100.,0.,100.)


def single_window_components(actual_cs, theoretical_cs, actual_xp_share, pressure_value,
                             pressure_upper_bound, state_values_a=None, state_values_b=None,
                             matchup_prior_a=None, execution_layers=None,
                             execution_weights=None, endpoint_vector=None):
    """Return auditable component scores for one replay window.

    ``pressure_value`` is the opponent cost actually caused during eligible
    last-hit free windows, while its upper bound is the same opportunity set's
    feasible maximum. State values may be normalized numeric reserves or state
    objects accepted by ``state_utility_share``; the latter include floor and
    within-window recoverability.
    """
    cs=_score_ratio(actual_cs,theoretical_cs,'CS')
    xp=_optional_score_ratio(actual_xp_share,1.,'XP')
    pressure=_optional_score_ratio(pressure_value,pressure_upper_bound,'pressure')
    if not isinstance(state_values_a,dict) or not isinstance(state_values_b,dict):
        state=None
    else:
        keys=set(state_values_a)&set(state_values_b)
        state={key:(state_utility_share(state_values_a[key],state_values_b[key],key)
                    if isinstance(state_values_a[key],dict) or isinstance(state_values_b[key],dict)
                    else relative_share(state_values_a[key],state_values_b[key],key))
               for key in sorted(keys)}
    state_score=sum(state.values())/len(state) if state else None
    matchup=matchup_adjusted_score(state_score,matchup_prior_a) if state_score is not None and matchup_prior_a is not None else None
    used={'cs':.30,'xp':.15,'pressure':.40,'state':.10,'matchup':.05}
    values={'cs':cs,'xp':xp,'pressure':pressure,'state':state_score,'matchup':matchup}
    available=[key for key in used if values[key] is not None]
    strategy=sum(used[key]*values[key] for key in available)/sum(used[key] for key in available)
    result=dict(cs=cs,xp=xp,pressure=pressure,state=state,state_score=state_score,
                matchup=matchup,strategy_score=strategy,weights=used,missing=[key for key in used if values[key] is None])
    if execution_layers is not None:
        strategy_layers={key:(None if values[key] is None else 2.*values[key]/100.-1.) for key in used}
        result['layered_score']=final_layer_score(strategy_layers,execution_layers,
            strategy_weights=used,execution_weights=execution_weights,endpoint_vector=endpoint_vector)
    else:
        result['layered_score']=None
    return result

def two_layer_score(strategy,execution,omega=.5,confidence=1.):
    """Published two-layer score with a frozen 50:50 strategy/execution mix."""
    if not math.isclose(float(omega), .5, abs_tol=1e-12):raise ValueError("published layer weight is fixed at omega=0.50")
    if not 0<=confidence<=1:raise ValueError("confidence must be in [0,1]")
    strategy_weights={"window":.25,"resource_plan":.20,"cooldown_discipline":.15,"cost_conversion":.15,"passive":.10,"rune":.05,"adaptation":.10}
    execution_weights={"distance":.35,"phase":.20,"resource":.20,"movement":.15,"timing":.10}
    def layer(data,weights):
        used={};missing=[]
        for key,weight in weights.items():
            value=data.get(key) if isinstance(data,dict) else None
            if value is None:missing.append(key);continue
            used[key]=max(0.,min(1.,_finite(value,key)))*weight
        denominator=sum(weights[k] for k in used)
        return (sum(used.values())/denominator if denominator else None),missing
    k,kmissing=layer(strategy,strategy_weights);o,omissing=layer(execution,execution_weights)
    if k is None or o is None:return dict(score=None,strategy_score=k,execution_score=o,missing=kmissing+omissing,confidence=confidence)
    score=100*(omega*k+(1-omega)*o)*confidence
    return dict(score=score,strategy_score=k,execution_score=o,omega=omega,confidence=confidence,
        missing=kmissing+omissing,interval=[max(0.,score-15*(1-confidence)),min(100.,score+15*(1-confidence))])


def evaluate_policy_branches(branches,side,weights=None,scales=None,alpha=.2,lambda_risk=.25):
    """Attach pre-decision Q values to compare branches and report regret."""
    rows=[]
    for branch in branches:
        metrics=branch.get("metrics",{}).get(side,{})
        q=decision_value([dict(probability=1.,metrics=metrics)],weights,scales,alpha,lambda_risk,
                         eligible=branch.get('eligible',True),
                         eligibility_reasons=branch.get('eligibility_reasons'))
        rows.append(dict(policy=branch[side+'_policy'],**q))
    rankable=[row for row in rows if row.get('decision_value') is not None]
    best=max(rankable,key=lambda x:x["decision_value"]) if rankable else None
    for row in rows:
        row["regret"]=(best["decision_value"]-row["decision_value"]) if best and row.get('decision_value') is not None else None
    return dict(side=side,branches=rows,best_policy=best["policy"] if best else None)

