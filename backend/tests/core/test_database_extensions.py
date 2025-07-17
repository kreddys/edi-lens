# FILE: backend/tests/core/test_database_extensions.py
import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

# Mark all tests in this file as integration tests that need the database
pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


@pytest.mark.run(order=1) # Run this test first to validate the foundation
async def test_pgvector_extension_is_active(db_session):
    """
    Tests that the 'pgvector' extension is installed and usable by attempting
    to cast an array to the 'vector' type.
    """
    try:
        # This simple query will fail if the 'vector' type is not defined.
        await db_session.execute(text("SELECT '[1,2,3]'::vector;"))
        # If the query succeeds, flush the session to ensure no pending state
        await db_session.flush()
        assert True, "pgvector extension is active and vector type is recognized."
    except ProgrammingError as e:
        # If a ProgrammingError occurs, it's likely the extension is missing.
        pytest.fail(f"pgvector extension test failed. The 'vector' type may not be available. Error: {e}")
    except Exception as e:
        pytest.fail(f"An unexpected error occurred while testing pgvector: {e}")

@pytest.mark.run(order=2) # Run this after the pgvector check
async def test_apache_age_extension_is_active(db_session):
    """
    Tests that the 'age' extension is installed and usable by creating a graph
    and executing a simple Cypher query.
    """
    try:
        # Apache AGE requires loading the extension and setting the search path for each session
        await db_session.execute(text("LOAD 'age';"))
        await db_session.execute(text("SET search_path = ag_catalog, '$user', public;"))
        
        # Check if the graph exists, and create it if it doesn't.
        # This makes the test idempotent (runnable multiple times).
        graph_exists = await db_session.execute(text("SELECT count(*) FROM ag_graph WHERE name = 'test_graph';"))
        if graph_exists.scalar_one() == 0:
            await db_session.execute(text("SELECT create_graph('test_graph');"))

        # Execute a simple Cypher query. This will fail if AGE is not working correctly.
        await db_session.execute(text("SELECT * from cypher('test_graph', $$ MATCH (n) RETURN n $$) as (v agtype);"))
        
        # If all commands succeed, the test passes.
        assert True, "Apache AGE extension is active and Cypher queries can be executed."
    except ProgrammingError as e:
        pytest.fail(f"Apache AGE extension test failed. It might not be loaded or installed correctly. Error: {e}")
    except Exception as e:
        pytest.fail(f"An unexpected error occurred while testing Apache AGE: {e}")