def score_subsequence(query: str, target: str) -> int:
    """
    Returns a score for how well the query matches the target as a subsequence.
    Higher score is better. Returns -1 if it's not a subsequence.
    """
    if not query:
        return 0
        
    query = query.lower()
    target = target.lower()
    
    if query == target:
        return 1000
        
    if query in target:
        if target.startswith(query):
            return 500
        return 400
        
    query_idx = 0
    skipped_chars = 0
    last_match_idx = -1
    
    for i, char in enumerate(target):
        if query_idx < len(query) and char == query[query_idx]:
            if last_match_idx != -1:
                skipped_chars += (i - last_match_idx - 1)
            last_match_idx = i
            query_idx += 1
            
    if query_idx == len(query):
        # Score based on skipped characters.
        return max(10, 100 - skipped_chars)
        
    return -1

def get_fuzzy_matches(query: str, options: list, format_func=None) -> list:
    """
    Returns a list of options sorted by how well they match the query.
    If format_func is provided, it also checks against the formatted names.
    """
    if not query:
        return sorted(list(options))[:25]
        
    scored_options = []
    seen = set()
    
    for opt in options:
        if opt in seen:
            continue
        seen.add(opt)
        
        opt_score = score_subsequence(query, opt)
        fmt_score = -1
        if format_func:
            fmt_score = score_subsequence(query, format_func(opt))
            
        best_score = max(opt_score, fmt_score)
        if best_score >= 0:
            scored_options.append((best_score, opt))
            
    # Sort by score, then length.
    scored_options.sort(key=lambda x: (x[0], -len(x[1])), reverse=True)
    return [opt for score, opt in scored_options][:25]

def fuzzy_find(query: str, options: list, format_func=None) -> str:
    """
    Returns the single best match for the query, or an empty string if none found.
    """
    matches = get_fuzzy_matches(query, options, format_func)
    return matches[0] if matches else ""
