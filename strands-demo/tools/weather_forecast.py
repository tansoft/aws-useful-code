from strands import Agent, tool

# 方式一：直接以 @tool 装饰器来声明，注释中解释函数和参数的用法
@tool
def weather_forecast(city: str, days: int = 3) -> str:
    """
    Get weather forecast for a city.
    Args:
        city: The name of the city
        days: Number of days for the forecast
    Returns:
        str: Weather forecast result.
    Raises:
        ValueError: If the city is invalid.
    """
    return f"Weather forecast for {city} for the next {days} days..."
