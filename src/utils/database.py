"""Database utility — schema introspection and SQL execution."""
import os

try:
    import psycopg2
    _HAS_PSYCOPG = True
except ImportError:
    _HAS_PSYCOPG = False


class DatabaseUtil:
    """Lightweight database wrapper for schema introspection and query execution."""

    def __init__(self, db_config: dict):
        self.db_config = db_config
        self.connection = None
        try:
            if _HAS_PSYCOPG:
                self.connection = psycopg2.connect(**db_config)
            else:
                raise ImportError("psycopg2 not installed")
        except Exception as e:
            print(f"Database connection error: {e}")
            raise

    def schema_details(self, schema_name: str = "public") -> str:
        """Return a text summary of all tables, columns, data types, and sample data."""
        connection = self.connection
        cursor = connection.cursor()
        schema_info_context = f"Database schema: {schema_name}\n\n"
        try:
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s", (schema_name,))
            tables_list = cursor.fetchall()
            for table_row in tables_list:
                table_name = table_row[0]
                schema_info_context += f"Table: {table_name}\n"
                cursor.execute("""SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position""", (schema_name, table_name))
                columns_list = cursor.fetchall()
                for col_row in columns_list:
                    schema_info_context += f"  - {col_row[0]}: {col_row[1]}\n"
                cursor.execute(f"SELECT * FROM {schema_name}.{table_name} LIMIT 5")
                sample_data = cursor.fetchall()
                schema_info_context += f"  Sample data:\n"
                for row in sample_data:
                    schema_info_context += f"    {row}\n"
                schema_info_context += "\n"
        except Exception as e:
            print(f"Schema details error: {e}")
            raise
        finally:
            cursor.close()
        return schema_info_context

    def execute_query(self, query: str) -> list:
        connection = self.connection
        cursor = connection.cursor()
        result = []
        try:
            cursor.execute(query)
            result = cursor.fetchall()
            connection.commit()
        except Exception as e:
            print(f"Query execution error: {e}")
            raise
        finally:
            cursor.close()
        return result

    def close(self):
        if self.connection:
            self.connection.close()
