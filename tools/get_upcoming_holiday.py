import datetime
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Tool configuration
name = "get_upcoming_holiday"
emoji = "📅"
description = (
    "Fetch the next statutory holiday at Hypha between a given start date and end date. "
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
    "required": []  # Changed from ["start_date"] to make it more flexible
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
    start = start_date.date() if isinstance(start_date, datetime.datetime) else start_date
    end = end_date.date() if isinstance(end_date, datetime.datetime) else end_date

    upcoming_holidays = [
        holiday for holiday in STATUTORY_HOLIDAYS if start <= holiday["date"] <= end
    ]

    return upcoming_holidays[:limit]


async def tool(roo, arguments, user):
    """
    Tool function to get upcoming holidays.
    
    Args:
        roo: RooLLM instance
        arguments: Dictionary of arguments from the LLM
        user: User identifier
        
    Returns:
        Dictionary with holiday information
    """
    
    try:
        # Handle parameter variations to make the tool more robust
        start_date_str = None
        if "start_date" in arguments:
            start_date_str = arguments["start_date"]
        elif "date_from" in arguments:
            start_date_str = arguments["date_from"]
        
        end_date_str = None
        if "end_date" in arguments:
            end_date_str = arguments["end_date"]
        elif "date_to" in arguments:
            end_date_str = arguments["date_to"]
            
        # Use default start date if not provided
        if not start_date_str:
            start_date_str = datetime.datetime.now().strftime("%Y-%m-%d")

        # Parse start date
        try:
            start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        except ValueError as e:
            return {
                "error": f"Invalid start date format: {start_date_str}. Please use YYYY-MM-DD format.",
                "message": "I couldn't understand the start date format. Please provide dates in YYYY-MM-DD format."
            }
            
        # Get limit parameter with default and bounds
        try:
            limit = max(1, min(10, int(arguments.get("limit", 1))))
        except (ValueError, TypeError):
            limit = 1
        
        # Use the provided end_date or set a default of one year from the start_date
        if end_date_str:
            try:
                end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d")
            except ValueError:
                # Still proceed with a default end date
                end_date = start_date + datetime.timedelta(days=365)
        else:
            end_date = start_date + datetime.timedelta(days=365)
            
        # Call the function to get holidays
        upcoming_holidays = get_upcoming_holidays(start_date, end_date, limit=limit)

        if not upcoming_holidays:
            # Format dates in a more natural way
            start_str = start_date.strftime("%B %d, %Y")
            end_str = end_date.strftime("%B %d, %Y")
            return {
                "message": f"There are no statutory holidays at Hypha between {start_str} and {end_str}."
            }

        # Format the response
        holidays_formatted = [
            {
                "name": holiday["name"],
                "date": holiday["date"].strftime("%Y-%m-%d"),
                "formatted_date": holiday["date"].strftime("%B %d, %Y")
            }
            for holiday in upcoming_holidays
        ]
        
        # If fewer holidays are found than requested, adjust the response
        message = None
        if len(upcoming_holidays) < limit and limit > 1:
            message = f"Found {len(upcoming_holidays)} statutory holidays at Hypha in the given date range."
        
        # Format the response based on the number of holidays found
        if len(upcoming_holidays) == 1:
            holiday = holidays_formatted[0]
            return {
                "holidays": holidays_formatted,
                "message": f"The next statutory holiday at Hypha is {holiday['name']} on {holiday['formatted_date']}."
            }
        else:
            # Format multiple holidays in a list
            holiday_list = "\n".join([f"• {h['name']} on {h['formatted_date']}" for h in holidays_formatted])
            return {
                "holidays": holidays_formatted,
                "count": len(holidays_formatted),
                "message": f"Here are the upcoming statutory holidays at Hypha:\n{holiday_list}"
            }
            
    except Exception as e:
        logger.error(f"Error in get_upcoming_holiday: {str(e)}", exc_info=True)
        return {
            "error": f"Failed to retrieve holidays: {str(e)}",
            "message": "I encountered an error while trying to find holidays. Please try again or rephrase your question."
        }