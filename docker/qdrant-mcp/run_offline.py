"""Entry wrapper for qdrant-mcp that makes the embedding model load from the image cache.

The pinned mcp-server-qdrant constructs fastembed.TextEmbedding(model_name) without
local_files_only, so fastembed tries HuggingFace/GCS on every start. This wrapper
defaults local_files_only=True (the model is pre-fetched at build time into
FASTEMBED_CACHE_PATH), then runs the unmodified server entry point. Nothing in the
pinned source is changed. If the configured EMBEDDING_MODEL was not pre-fetched at
build time, startup fails with a clear error instead of reaching the network.
"""

import sys

from fastembed import TextEmbedding

_original_init = TextEmbedding.__init__


def _offline_init(self, *args, **kwargs):
    kwargs.setdefault("local_files_only", True)
    _original_init(self, *args, **kwargs)


TextEmbedding.__init__ = _offline_init

from mcp_server_qdrant.main import main  # noqa: E402

if __name__ == "__main__":
    sys.argv[0] = "mcp-server-qdrant"
    main()
