"""Shared input helpers for the diffusion scripts. No user paths are stored in code."""
import os
import sys


def photo_path(arg=None):
    """Return the source photo path: the given argument, or asked on the console if missing."""
    path = arg or input("Photo path: ")
    path = path.strip().strip('"').strip("'")
    if not os.path.isfile(path):
        sys.exit(f"Not a file: {path}")
    return path
