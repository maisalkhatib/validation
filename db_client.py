import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from typing import Optional, Dict, List
from contextlib import contextmanager

class DatabaseClient:
    def __init__(self, connection_string: str):
        """
        Initialize database client
        Args:
            connection_string: PostgreSQL connection string
            Example: "dbname=barns_inventory user=postgres password=QSS2030QSS host=localhost port=5432"
        """
        self.connection_string = connection_string
        self.logger = logging.getLogger(__name__)
        
        # Test connection on initialization
        try:
            with self._get_connection() as conn:
                self.logger.info("Database connection successful")
        except Exception as e:
            self.logger.error(f"Failed to connect to database: {e}")
            raise
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = psycopg2.connect(self.connection_string)
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def get_inventory(self, ingredient_type: str, subtype: str) -> Optional[Dict]:
        """
        Get inventory data for a specific ingredient
        Args:
            ingredient_type: Type of ingredient (coffee_beans, cups, milk, syrup)
            subtype: Subtype (regular, H9, whole, vanilla, etc.)
        Returns:
            Dictionary with current_amount or None if not found
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    query = """
                        SELECT current_amount , last_updated
                        FROM inventory 
                        WHERE ingredient_type = %s AND subtype = %s
                    """
                    cursor.execute(query, (ingredient_type, subtype))
                    result = cursor.fetchone()
                    
                    if result:
                        return {
                            "current_amount": float(result['current_amount']),
                            "last_updated": result['last_updated']
                        }
                    else:
                        self.logger.warning(f"No inventory found for {ingredient_type}:{subtype}")
                        return None
                        
        except Exception as e:
            self.logger.error(f"Error getting inventory for {ingredient_type}:{subtype}: {e}")
            return None
    
    def update_inventory(self, ingredient_type: str, subtype: str, new_amount: float) -> bool:
        """
        Update the current amount for an ingredient with pessimistic locking
        Args:
            ingredient_type: Type of ingredient
            subtype: Subtype
            new_amount: New amount to set
        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # First, lock the specific row to prevent race conditions
                    lock_query = """
                        SELECT current_amount 
                        FROM inventory 
                        WHERE ingredient_type = %s AND subtype = %s
                        FOR UPDATE
                    """
                    cursor.execute(lock_query, (ingredient_type, subtype))
                    locked_row = cursor.fetchone()
                    
                    if not locked_row:
                        self.logger.warning(f"No inventory found to lock for {ingredient_type}:{subtype}")
                        return False
                    
                    # Now update the locked row
                    update_query = """
                        UPDATE inventory 
                        SET current_amount = %s, last_updated = CURRENT_TIMESTAMP
                        WHERE ingredient_type = %s AND subtype = %s
                    """
                    cursor.execute(update_query, (new_amount, ingredient_type, subtype))
                    
                    if cursor.rowcount > 0:
                        self.logger.info(f"Updated {ingredient_type}:{subtype} to {new_amount}")
                        return True
                    else:
                        self.logger.warning(f"No rows updated for {ingredient_type}:{subtype}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Error updating amount for {ingredient_type}:{subtype}: {e}")
            return False
            
    def check_connection(self) -> bool:
        """
        Test if database connection is working
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return True
        except Exception as e:
            self.logger.error(f"Connection check failed: {e}")
            return False


# Example usage:
if __name__ == "__main__":
    # Initialize client
    db_client = DatabaseClient(
        "dbname=barns_inventory user=postgres password=QSS2030QSS host=localhost port=5432"
    )
    
    # Get specific inventory
    coffee_inventory = db_client.get_inventory("coffee_beans", "regular")
    print(f"Regular coffee beans: {coffee_inventory}")
    
    # Update amount
    success = db_client.update_inventory("coffee_beans", "regular", 2600.0)
    print(f"Update successful: {success}")

    # update the inventory for milk
    success = db_client.update_inventory("milk", "whole", 2600.0)
    print(f"Update successful: {success}")

    # update the inventory for milk
    success = db_client.update_inventory("milk", "whole", 2600.0)
    print(f"Update successful: {success}")