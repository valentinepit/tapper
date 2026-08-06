import os

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

WPLAN_LOGIN = os.environ["WPLAN_LOGIN"]
WPLAN_PASS = os.environ["WPLAN_PASS"]

LOGIN_QUERY_HASH = os.environ["LOGIN_QUERY_HASH"]
VACATIONS_QUERY_HASH = os.environ["VACATIONS_QUERY_HASH"]
START_FINISH_QUERY_HASH = os.environ["START_FINISH_QUERY_HASH"]
ABSENCES_QUERY_HASH = os.environ["ABSENCES_QUERY_HASH"]