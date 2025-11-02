#!/usr/bin/env python3
"""
Recurrence utilities for normalizing event titles into recurrence keys.
"""

import re


def normalize_recurrence_key(title: str) -> str:
    """
    Normalize event title into a recurrence key for grouping recurring events.
    
    Algorithm:
    1. Convert to lowercase
    2. Trim whitespace
    3. Collapse multiple whitespace to single space
    4. Strip punctuation
    
    Args:
        title: Event title to normalize
        
    Returns:
        Normalized recurrence key
        
    Examples:
        "Trivia Night" -> "trivia night"
        "Trivia  Night!!!" -> "trivia night"
        "Comedy Show: Open Mic" -> "comedy show open mic"
    """
    if not title:
        return ""
    
    # Convert to lowercase
    normalized = title.lower().strip()
    
    # Collapse multiple whitespace to single space
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Strip punctuation (keep alphanumeric and spaces only)
    normalized = re.sub(r'[^\w\s]', '', normalized)
    
    # Final trim
    normalized = normalized.strip()
    
    return normalized

