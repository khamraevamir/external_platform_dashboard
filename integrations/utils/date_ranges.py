import calendar
from datetime import datetime


def get_current_month_date_range(today=None):
    today = today or datetime.today()

    first_day = today.replace(day=1)

    last_day_num = calendar.monthrange(today.year, today.month)[1]
    last_day = today.replace(day=last_day_num)

    return first_day, last_day


def format_date_range_for_smartup(today=None):
    first_day, last_day = get_current_month_date_range(today=today)

    return (
        first_day.strftime("%d.%m.%Y"),
        last_day.strftime("%d.%m.%Y"),
    )