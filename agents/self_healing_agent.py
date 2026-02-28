from agents.sql_generator import generate_sql_query_dbcs
from utils.query_validator import is_query_valid
from utils.llm import call_claude_text as call_claude
import os
from databricks import sql
import re

MAX_RETRIES = 1


def get_database_schema_context(catalog_name: str, schema_name: str) -> str:
    """
    Fetches the full DDL (Create Table statements) for the tables.
    This gives the LLM types, primary keys, and table comments.
    """
    try:
        from databricks.connect import DatabricksSession
        spark = DatabricksSession.builder.serverless(True).getOrCreate()
        
        # 1. Get the list of tables in this schema
        tables_df = spark.sql(f"SHOW TABLES IN {catalog_name}.{schema_name}").toPandas()
        
        if tables_df.empty:
            return f"Error: No tables found in {catalog_name}.{schema_name}."

        context = "Here is the schema DDL for the relevant tables in this database:\n\n"
        
        # 2. For the most relevant tables, get their 'SHOW CREATE TABLE' output
        # We'll focus on these to keep the prompt size efficient
        target_tables = ['orders', 'customer', 'lineitem', 'nation', 'region', 'supplier']
        
        for table_name in tables_df['tableName']:
            if table_name in target_tables:
                # This command returns the exact SQL used to create the table, including all metadata
                ddl = spark.sql(f"SHOW CREATE TABLE {catalog_name}.{schema_name}.{table_name}").collect()[0][0]
                context += f"-- Table structure for {table_name}:\n{ddl}\n\n"
            
        return context
        
    except Exception as e:
        return f"Error fetching DDL: {str(e)}"


import re

def clean_sql(raw_sql: str) -> str:
    """
    Extracts ONLY the SQL query, handling conversational noise and 
    nested backticks accurately.
    """
    if not raw_sql:
        return ""

    # 1. Targeted extraction for Markdown blocks
    # This looks for ```sql ... ``` or just ``` ... ```
    # It uses a non-greedy dot (.*?) to stop at the VERY FIRST closing backtick.
    block_match = re.search(r"```(?:sql|SQL)?\s*(.*?)\s*```", raw_sql, re.DOTALL | re.IGNORECASE)
    
    if block_match:
        sql = block_match.group(1).strip()
    else:
        # 2. Fallback: If no backticks, find the first occurrence of a SQL keyword 
        # and capture until the end of that "thought" (usually a semicolon or double newline)
        # We look for SELECT, WITH, or CREATE.
        fallback_match = re.search(r"(\b(?:SELECT|WITH|CREATE|UPDATE|DELETE)\b.*)", raw_sql, re.IGNORECASE | re.DOTALL)
        sql = fallback_match.group(1).strip() if fallback_match else raw_sql.strip()

    # 3. Post-processing Cleanup
    # Remove trailing semicolons (Databricks/Spark handles single queries better without them)
    sql = re.sub(r';\s*$', '', sql)
    
    # Remove any line-level comments that might have been accidentally captured if the LLM 
    # put them on the same line as the closing backticks
    sql = sql.split("```")[0].strip()
    
    return sql
    

def generate_safe_sql(prompt: str, catalog_name: str, schema_name: str) -> dict:
    """
    Self-healing SQL generation with detailed debug tracing.
    """
    result = {
        "sql": None,
        "valid": False,
        "source": "None",
        "error": "None",
        "retried": False,
        "debug_trace": {} # We will store everything here
    }

    # 1. Fetch Schema
    schema_context = get_database_schema_context(catalog_name, schema_name)
    result["debug_trace"]["schema_used"] = schema_context
    
    if schema_context.startswith("Error"):
        result["error"] = schema_context
        return result

    # 2. Try Databricks AI (Primary)
    enriched_db_prompt = f"{schema_context}\n\nUser Request: {prompt}"

    
    result["debug_trace"]["dbcs_input"] = enriched_db_prompt
    
    # print(f"--- DBCS INPUT ---\n{enriched_db_prompt}")
    
    sql_candidate = generate_sql_query_dbcs(enriched_db_prompt)
    #result["debug_trace"]["dbcs_output"] = sql_candidate
    
    # parse the response
    sql_candidate = clean_sql(sql_candidate)
    
    #print(f"--- DBCS OUTPUT ---\n{sql_candidate}")

    # 3. Validate
    if is_query_valid(sql_candidate):
        result["sql"] = sql_candidate
        result["valid"] = True
        result["source"] = "databricks_ai"
        return result

    # 4. Fallback to Claude
    result["retried"] = True
    #result["debug_trace"]["validation_failure"] = f"DBCS SQL was invalid: {sql_candidate}"
    
    print(f"Validation Failed, falling back to Claude")

    for attempt in range(MAX_RETRIES):
        # We'll log what we send to Claude
        result["debug_trace"][f"claude_attempt_{attempt+1}_input"] = {
            "prompt": prompt,
            "schema": schema_context
        }
        
        sql_system_prompt = (
            "You are a Senior SQL Architect. Return ONLY the raw SQL query. "
            "Do not include any explanation, markdown, or formatting.\n\n"
            f"{schema_context}"
        )

        sql_candidate = call_claude(
            user_prompt=prompt,
            system_prompt=sql_system_prompt
        )
        # parse the response
        sql_candidate = clean_sql(sql_candidate)
        
        # result["debug_trace"][f"claude_attempt_{attempt+1}_output"] = sql_candidate
        # print(f"--- CLAUDE OUTPUT (Attempt {attempt+1}) ---\n{sql_candidate}")

        if is_query_valid(sql_candidate):
            result["sql"] = sql_candidate
            result["valid"] = True
            result["source"] = "claude_fallback"
            return result

    result["error"] = "Both generators failed to produce valid SQL."
    return result