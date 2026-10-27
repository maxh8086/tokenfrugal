import re

def slugify(s: str) -> str:
    """
    Converts a string into a URL-friendly slug.
    Lowercase, strip, collapse runs of non-alphanumerics into a single '-', 
    no leading or trailing '-'.
    """
    # Lowercase
    s = s.lower()
    
    # Replace runs of non-alphanumeric characters with a single hyphen
    s = re.sub(r'[^a-z0-9]+', '-', s)
    
    # Strip leading or trailing hyphens
    s = s.strip('-')
    
    return s