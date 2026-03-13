def parse_number(value):
    if value in (None, "", "-"):
        return 0.0

    value = str(value).strip()
    value = value.replace("\xa0", "")
    value = value.replace(" ", "")
    value = value.replace(",", ".")

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0