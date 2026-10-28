"""Native caption templates verified in Sketchpad 5.06; no desktop input here."""

FORMULAS = ('curve_k1', 'curve_k2', 'area_difference', 'area_half_difference',
            'area_sum', 'area_half_sum')


def caption_plan(formula, fraction_button=None, subscript_button=None):
    if formula not in FORMULAS:
        raise ValueError('Unknown formula template')
    actions = []

    def click(point):
        if (not isinstance(point, list) or len(point) != 2
                or any(type(v) is not int for v in point)):
            raise ValueError('Supply the template button [x,y] from the current screenshot')
        actions.append({'tool': 'sketchpad_click', 'args': {'x': point[0], 'y': point[1]}})

    def text(value):
        actions.append({'tool': 'sketchpad_type_literal', 'args': {'text': value}})

    def key(value):
        actions.append({'tool': 'sketchpad_key', 'args': {'key': value}})

    def fraction(numerator, denominator):
        click(fraction_button)
        text(numerator)
        key('tab')
        text(denominator)
        key('right')
        key('right')

    if formula.startswith('curve_'):
        text('y = ')
        fraction('k₁' if formula == 'curve_k1' else 'k₂', 'x')
    else:
        click(subscript_button)
        text('S')
        key('tab')
        text('阴影')
        key('right')
        key('right')
        text(' = ')
        if formula == 'area_half_difference':
            fraction('|k₁|', '2')
            text(' − ')
            fraction('|k₂|', '2')
        elif formula == 'area_half_sum':
            fraction('|k₁| + |k₂|', '2')
        else:
            text('|k₁| '+('−' if formula == 'area_difference' else '+')+' |k₂|')
    return actions
