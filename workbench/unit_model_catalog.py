"""Local minion-model catalog and generic bar-size classification."""
from pathlib import Path


MODEL_PATTERNS={
    'melee':('Melee',), 'caster':('Caster',), 'siege':('Siege',), 'super':('Super',)
}


def discover_model_templates(root=None):
    root=Path(root or Path(__file__).resolve().parents[2])/'unit_model'
    result=[]
    for path in sorted(root.glob('*')):
        if path.suffix.lower() not in {'.png','.jpg','.jpeg','.webp'}:continue
        kind=next((kind for kind,parts in MODEL_PATTERNS.items() if all(part.lower() in path.name.lower() for part in parts)),None)
        if kind:result.append({'kind':kind,'path':str(path),'template_only':True})
    return result


def classify_bar_size(width_px, *, hero_min_width=70, minion_max_width=69):
    """Return a weak class prior; it is not an identity confirmation."""
    if width_px is None:return {'kind':'unknown','confidence':0.0}
    width=float(width_px)
    if width>=hero_min_width:return {'kind':'hero','confidence':min(.95,.55+(width-hero_min_width)/200)}
    if width<=minion_max_width:return {'kind':'minion','confidence':min(.9,.55+(minion_max_width-width)/200)}
    return {'kind':'unknown','confidence':.2}
