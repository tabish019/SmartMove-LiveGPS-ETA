"""Small, explainable fuzzy-inference ETA estimator for SmartMove.

This is a zero-order Sugeno-style system: overlapping membership functions
for distance and speed activate rules, and the consequent ETA values are
combined using a weighted average. Inputs are approximate, so ETA is an
estimate, not a guaranteed arrival time.
"""

def triangle(x, a, b, c):
    if x < a or x > c:
        return 0.0
    if x == b:
        return 1.0
    if x < b:
        return (x - a) / (b - a) if b != a else 1.0
    return (c - x) / (c - b) if c != b else 1.0

def left_shoulder(x, a, b):
    if x <= a: return 1.0
    if x >= b: return 0.0
    return (b - x) / (b - a)

def right_shoulder(x, a, b):
    if x <= a: return 0.0
    if x >= b: return 1.0
    return (x - a) / (b - a)

def fuzzy_eta(distance_km, speed_kmh):
    """Return estimated minutes, distance memberships, speed band and traffic band."""
    distance_km = max(0.0, min(float(distance_km), 100.0))
    speed_kmh = max(0.0, min(float(speed_kmh), 120.0))
    dist = {
        'near': max(left_shoulder(distance_km, 0.0, 1.5), triangle(distance_km, 0.0, 0.0, 1.5)),
        'medium': triangle(distance_km, 0.5, 3.0, 7.0),
        'far': right_shoulder(distance_km, 4.0, 10.0),
    }
    # Overlapping speed sets handle imprecise/variable urban traffic.
    speed = {
        'slow': left_shoulder(speed_kmh, 8.0, 22.0),
        'normal': triangle(speed_kmh, 12.0, 30.0, 48.0),
        'fast': right_shoulder(speed_kmh, 35.0, 55.0),
    }
    # Rule consequents are minutes for each distance category at normal speed.
    distance_minutes = {'near': 3.0, 'medium': 8.0, 'far': 16.0}
    speed_factor = {'slow': 1.75, 'normal': 1.0, 'fast': 0.75}
    numerator = denominator = 0.0
    for d_name, d_mu in dist.items():
        for s_name, s_mu in speed.items():
            strength = min(d_mu, s_mu)  # Mamdani-style AND for rule activation
            consequent = distance_minutes[d_name] * speed_factor[s_name]
            numerator += strength * consequent
            denominator += strength
    # If GPS reports zero speed or memberships are at an edge, use a safe baseline.
    eta = numerator / denominator if denominator else max(1.0, (distance_km / max(speed_kmh, 8.0)) * 60.0)
    eta = max(1, int(round(eta)))
    traffic = 'High' if speed_kmh < 15 else ('Medium' if speed_kmh < 30 else 'Low')
    speed_band = 'Slow' if speed_kmh < 15 else ('Normal' if speed_kmh < 35 else 'Fast')
    return {'eta_minutes': eta, 'distance_km': round(distance_km, 2), 'speed_kmh': round(speed_kmh, 1),
            'traffic': traffic, 'speed_band': speed_band, 'method': 'Fuzzy inference (distance × speed rules)'}
