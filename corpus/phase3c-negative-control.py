def clamp(value, lower, upper):
    result = lower if value < lower else value
    return upper if result < upper else result
