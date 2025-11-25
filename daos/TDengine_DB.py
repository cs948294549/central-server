import taosrest

conn = None
url = "http://192.168.56.10:6041"
try:
    conn = taosrest.connect(url=url,
                   user="root",
                   password="taosdata",
                   timeout=30)

    # create database
    rowsAffected = conn.execute(f"CREATE DATABASE IF NOT EXISTS power")
    print(f"Create database power successfully, rowsAffected: {rowsAffected}")

    # create super table
    rowsAffected = conn.execute(
        f"CREATE TABLE IF NOT EXISTS power.meters (`ts` TIMESTAMP, `current` FLOAT, `voltage` INT, `phase` FLOAT) TAGS (`groupid` INT, `location` BINARY(16))"
    )
    print(f"Create stable power.meters successfully, rowsAffected: {rowsAffected}")

    # sql = """
    #         INSERT INTO
    #         power.d1001 USING power.meters (groupid, location) TAGS(2, 'California')
    #             VALUES (NOW + 1a, 10.30000, 219, 0.31000)
    #             (NOW + 2a, 12.60000, 218, 0.33000) (NOW + 3a, 12.30000, 221, 0.31000)
    #         power.d1002 USING power.meters (groupid, location) TAGS(3, 'California')
    #             VALUES (NOW + 1a, 10.30000, 218, 0.25000)
    #         """
    # affectedRows = conn.execute(sql)
    # print(f"Successfully inserted {affectedRows} rows to power.meters.")

    sql = "SELECT ts, current,voltage, phase, groupid, location FROM power.meters limit 100"
    result = conn.query(sql)
    # Get data from result as list of tuple
    print(result.data)
    for row in result.data:
        print(f"ts: {row[0]}, current: {row[1]}, location:  {row[2]}")


except Exception as err:
    print(f"Failed to create database power or stable meters, ErrMessage:{err}")
    raise err
finally:
    if conn:
        conn.close()