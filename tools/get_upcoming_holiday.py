import datetime

# Tool configuration
name = "get_upcoming_holiday"
emoji = "📅"
description = (
    "Fetch the next statutory holiday between a given start date and end date. "
    "Use this for direct queries about holidays, such as 'What is the next holiday?' or 'Are there holidays next month?'. "
    "If the user asks for multiple holidays, use the 'limit' parameter to specify the desired number of holidays."
)
parameters = {
    "type": "object",
    "properties": {
        "start_date": {
            "type": "string",
            "format": "date",
            "description": "The start date to search for holidays in YYYY-MM-DD format.",
            "default": datetime.datetime.now().strftime("%Y-%m-%d")
        },
        "end_date": {
            "type": "string",
            "format": "date",
            "description": "The end date to search for holidays in YYYY-MM-DD format."
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "description": "The maximum number of holidays to return. Defaults to 1 if not provided."
        }
    },
    "required": ["start_date"]
}


# Define statutory holidays
STATUTORY_HOLIDAYS = [
    {"name": "New Year's Day", "date": datetime.date(2025, 1, 1)},
    {"name": "Family Day", "date": datetime.date(2025, 2, 17)},
    {"name": "Good Friday", "date": datetime.date(2025, 4, 18)},
    {"name": "May Day (International Workers' Day)", "date": datetime.date(2025, 5, 1)},
    {"name": "Victoria Day", "date": datetime.date(2025, 5, 19)},
    {"name": "Canada Day", "date": datetime.date(2025, 7, 1)},
    {"name": "Civic Holiday", "date": datetime.date(2025, 8, 4)},
    {"name": "Labour Day", "date": datetime.date(2025, 9, 1)},
    {"name": "Thanksgiving", "date": datetime.date(2025, 10, 13)},
    {"name": "Remembrance Day", "date": datetime.date(2025, 11, 11)},
    {"name": "Christmas Day", "date": datetime.date(2025, 12, 25)},
    {"name": "Boxing Day", "date": datetime.date(2025, 12, 26)},
]

# Function to find the next holiday
def get_upcoming_holidays(start_date, end_date, limit=1):
    """

    Find the next `limit` statutory holidays between the given start_date and end_date.
    Args:
        start_date (datetime): The start date of the range.
        end_date (datetime): The end date of the range.
        limit (int): The number of holidays to return.
    Returns:
        list[dict]: A list of holidays or an empty list if no holidays are found.
    """
    start = start_date.date()
    end = end_date.date()

    upcoming_holidays = [
        holiday for holiday in STATUTORY_HOLIDAYS if start <= holiday["date"] <= end
    ]

    return upcoming_holidays[:limit]


async def tool(roo, arguments, user):
    try:
        # Parse input arguments
        start_date = datetime.datetime.strptime(arguments["start_date"], "%Y-%m-%d")
        end_date_str = arguments.get("end_date")
        limit = max(1, min(10, int(arguments.get("limit", 1))))  # Limit between 1 and 10

        # Use the provided `end_date` or set a default of one year from the `start_date`
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d")
        else:
            end_date = start_date + datetime.timedelta(days=365)

        # Call the updated function
        upcoming_holidays = get_upcoming_holidays(start_date, end_date, limit=limit)

        if not upcoming_holidays:
            return {"message": "No holidays found in the given date range."}

        # If fewer holidays are found than requested, adjust the response
        if len(upcoming_holidays) < limit:
            message = f"Only {len(upcoming_holidays)} holidays found in the given date range."
        else:
            message = None

        return {
            "holidays": [
                {"name": holiday["name"], "date": holiday["date"].strftime("%Y-%m-%d")}
                for holiday in upcoming_holidays
            ],
            "message": message,
        }
    except Exception as e:
        return {"error": f"Failed to retrieve holidays: {str(e)}"}
