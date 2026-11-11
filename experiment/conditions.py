"""The four conditions. Differences are listed explicitly so each comparison changes ONE thing."""
CONDITIONS = {
    # name:                 memory, note written after each episode,      retrieval
    "react":               {"memory": False, "note": None,         "retrieval": None},
    "react_mem":           {"memory": True,  "note": "reflection", "retrieval": "relevance"},
    "react_mem_noreflect": {"memory": True,  "note": "trajectory", "retrieval": "relevance"},  # ablates reflection
    "react_mem_recency":   {"memory": True,  "note": "reflection", "retrieval": "recency"},    # ablates retrieval
}
