# This file will contain the SQL generator agent. It will input the 
# prompt(natural language) and output the SQL query.

# You must add databricks-connect to your requirements.txt
from databricks.connect import DatabricksSession

# Initialize a remote Spark session. 
# Databricks Apps automatically handles the authentication via injected environment variables.
# This tells the app to use the Serverless compute attached to it
spark = DatabricksSession.builder.serverless(True).getOrCreate()

def generate_sql_query_dbcs(prompt: str) -> str:
    # Safely escape single quotes to prevent SQL syntax errors or injection
    safe_prompt = prompt.replace("'", "''")
    
    query = f"SELECT ai_gen('{safe_prompt}') AS generated_sql"
    
    try:
        df = spark.sql(query)
        # Extract the string result from the DataFrame
        return df.collect()[0]['generated_sql']
    except Exception as e:
        return f"Databricks AI Error: {str(e)}"


