import json
def recursive_dict(obj):
    try:
        if isinstance(obj, dict):
            return {key: recursive_dict(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [recursive_dict(element) for element in obj]
        elif hasattr(obj, '__dict__'):
            return recursive_dict(vars(obj))
        else:
            # Try JSON serialization to ensure it's serializable
            json.dumps(obj)
            return obj
    except Exception:
        return str(obj)