import os
import psycopg2


class LaundryDatabase:

    def __init__(self):
        self.connection = None

    def connect(self):

        if self.connection is not None:
            return

        self.connection = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            database=os.getenv("DB_NAME", "laundry_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "")
        )

    def save_task(
        self,
        command,
        target,
        confidence,
        saturation,
        value,
        classification,
        destination,
        status
    ):

        try:
            self.connect()

            cursor = self.connection.cursor()

            query = """
                INSERT INTO laundry_tasks
                (
                    command,
                    target,
                    confidence,
                    saturation,
                    value,
                    classification,
                    destination,
                    status
                )
                VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s)
            """

            cursor.execute(
                query,
                (
                    command,
                    target,
                    confidence,
                    saturation,
                    value,
                    classification,
                    destination,
                    status
                )
            )

            self.connection.commit()
            cursor.close()

            return True

        except Exception as e:

            print(f"[DATABASE ERROR] {e}")

            if self.connection:
                self.connection.rollback()

            return False

    def close(self):

        if self.connection:
            self.connection.close()
            self.connection = None