import uuid

def is_valid_uuid(val):
    if not val or val == "SYSTEM":
        return False
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False
