#!/usr/bin/env python3
"""Clear all Chroma collections. Use to reset before re-loading trails."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.shared.chroma import get_chroma_client
from beta_graph.servers.wta.config import CHROMA_COLLECTION_NAME as WTA_COLLECTION


def main():
    client = get_chroma_client()
    for name in [WTA_COLLECTION]:
        try:
            client.delete_collection(name)
            print(f"Deleted collection: {name}")
        except Exception as e:
            print(f"Skip {name}: {e}")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
