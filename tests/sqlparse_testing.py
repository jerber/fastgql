import sqlparse
from devtools import debug

parsed = sqlparse.parse(
    'select * from "Booking" WHERE "Booking".id = $1 ORDER BY "Booking".start_time LIMIT 10 OFFSET 1'
)
debug(parsed)
